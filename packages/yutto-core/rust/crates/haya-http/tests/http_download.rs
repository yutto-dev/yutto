use std::{
    sync::{Arc, Mutex},
    time::Duration,
};

use haya::{
    CommitSink, DownloadSpec, Downloader, RangeSource, SourceErrorKind,
    file::{FileOpenMode, FileSink},
};
use haya_http::HttpRangeSource;
use reqwest::{Client, Url, header::HeaderMap};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    task::JoinHandle,
};

#[derive(Clone, Copy)]
enum Behavior {
    Normal,
    IgnoreRange,
    WrongRange,
    Disconnect,
    GzipEncoding,
}

struct FaultServer {
    url: Url,
    requests: Arc<Mutex<Vec<String>>>,
    task: JoinHandle<()>,
}

impl FaultServer {
    async fn spawn(payload: Vec<u8>, behavior: Behavior) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .expect("bind fault server");
        let address = listener.local_addr().expect("local address");
        let payload = Arc::new(payload);
        let requests = Arc::new(Mutex::new(Vec::new()));
        let task_requests = requests.clone();
        let task = tokio::spawn(async move {
            loop {
                let Ok((socket, _)) = listener.accept().await else {
                    return;
                };
                let payload = payload.clone();
                let requests = task_requests.clone();
                tokio::spawn(async move {
                    serve_connection(socket, payload, behavior, requests).await;
                });
            }
        });
        Self {
            url: Url::parse(&format!("http://{address}/asset")).expect("server URL"),
            requests,
            task,
        }
    }

    fn source(&self, expected_size: u64) -> Arc<HttpRangeSource> {
        Arc::new(HttpRangeSource::new(
            Client::new(),
            self.url.clone(),
            HeaderMap::new(),
            expected_size,
        ))
    }

    fn requested_ranges(&self) -> Vec<String> {
        self.requests.lock().expect("request lock poisoned").clone()
    }
}

impl Drop for FaultServer {
    fn drop(&mut self) {
        self.task.abort();
    }
}

async fn serve_connection(
    mut socket: TcpStream,
    payload: Arc<Vec<u8>>,
    behavior: Behavior,
    requests: Arc<Mutex<Vec<String>>>,
) {
    let mut request = Vec::new();
    let mut buffer = [0_u8; 2048];
    loop {
        let Ok(read) = socket.read(&mut buffer).await else {
            return;
        };
        if read == 0 {
            return;
        }
        request.extend_from_slice(&buffer[..read]);
        if request.windows(4).any(|window| window == b"\r\n\r\n") {
            break;
        }
    }

    let request = String::from_utf8_lossy(&request);
    let range = request.lines().find_map(|line| {
        line.strip_prefix("Range: ")
            .or_else(|| line.strip_prefix("range: "))
            .map(str::trim)
    });
    requests
        .lock()
        .expect("request lock poisoned")
        .push(range.unwrap_or("<none>").to_owned());

    if matches!(behavior, Behavior::Disconnect) {
        return;
    }

    if matches!(behavior, Behavior::IgnoreRange) {
        write_response(&mut socket, "200 OK", &[], &payload).await;
        return;
    }

    let Some((start, end)) = range.and_then(parse_range) else {
        write_response(&mut socket, "400 Bad Request", &[], b"").await;
        return;
    };
    let end = end.min(payload.len());
    let content_start = if matches!(behavior, Behavior::WrongRange) {
        start + 1
    } else {
        start
    };
    let content_range = format!("bytes {content_start}-{}/{}", end - 1, payload.len());
    if matches!(behavior, Behavior::GzipEncoding) {
        const GZIP_1024_ZEROS: &[u8] = &[
            0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x63, 0x60, 0x18, 0x05,
            0xa3, 0x60, 0x14, 0x8c, 0x54, 0x00, 0x00, 0x2e, 0xaf, 0xb5, 0xef, 0x00, 0x04, 0x00,
            0x00,
        ];
        assert_eq!(payload.len(), 1024);
        write_response(
            &mut socket,
            "206 Partial Content",
            &[
                ("Content-Range", content_range),
                ("Content-Encoding", "gzip".to_owned()),
            ],
            GZIP_1024_ZEROS,
        )
        .await;
        return;
    }
    write_response(
        &mut socket,
        "206 Partial Content",
        &[("Content-Range", content_range)],
        &payload[start..end],
    )
    .await;
}

fn parse_range(value: &str) -> Option<(usize, usize)> {
    let value = value.strip_prefix("bytes=")?;
    let (start, end) = value.split_once('-')?;
    Some((
        start.parse().ok()?,
        end.parse::<usize>().ok()?.checked_add(1)?,
    ))
}

async fn write_response(
    socket: &mut TcpStream,
    status: &str,
    headers: &[(&str, String)],
    body: &[u8],
) {
    let mut head = format!(
        "HTTP/1.1 {status}\r\nContent-Length: {}\r\nConnection: close\r\n",
        body.len()
    );
    for (name, value) in headers {
        head.push_str(&format!("{name}: {value}\r\n"));
    }
    head.push_str("\r\n");
    socket
        .write_all(head.as_bytes())
        .await
        .expect("write response headers");
    socket.write_all(body).await.expect("write response body");
    socket.shutdown().await.expect("close response");
}

fn spec(expected_size: u64) -> DownloadSpec {
    DownloadSpec {
        expected_size,
        page_size: 1024,
        block_size: 4 * 1024,
        window_pages: 8,
        workers: 3,
        max_attempts: 2,
        source_cooldown: Duration::from_millis(1),
        attempt_timeout: Duration::from_secs(1),
    }
}

fn payload(size: usize) -> Vec<u8> {
    (0..size).map(|index| (index % 251) as u8).collect()
}

#[tokio::test]
async fn downloads_to_a_file_and_resumes_from_an_unaligned_length() {
    let expected = payload(20 * 1024 + 17);
    let server = FaultServer::spawn(expected.clone(), Behavior::Normal).await;
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    let prefix = 1237;
    tokio::fs::write(&path, &expected[..prefix])
        .await
        .expect("write prefix");
    let sink = Arc::new(
        FileSink::open(&path, FileOpenMode::ResumeFromLength)
            .await
            .expect("open file sink"),
    );

    let report = Downloader::new(
        spec(expected.len() as u64),
        vec![server.source(expected.len() as u64)],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("download succeeds");
    sink.close().await.expect("close output");

    assert_eq!(report.committed_bytes, expected.len() as u64);
    assert_eq!(tokio::fs::read(path).await.expect("read output"), expected);
    assert!(
        server
            .requested_ranges()
            .iter()
            .all(|range| range.starts_with("bytes=") && !range.ends_with('-'))
    );
}

#[tokio::test]
async fn switches_to_a_mirror_after_wrong_content_range() {
    let expected = payload(12 * 1024 + 3);
    let bad = FaultServer::spawn(expected.clone(), Behavior::WrongRange).await;
    let good = FaultServer::spawn(expected.clone(), Behavior::Normal).await;
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    let sink = Arc::new(
        FileSink::open(&path, FileOpenMode::Overwrite)
            .await
            .expect("open file sink"),
    );

    Downloader::new(
        spec(expected.len() as u64),
        vec![
            bad.source(expected.len() as u64),
            good.source(expected.len() as u64),
        ],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("healthy mirror finishes download");
    sink.close().await.expect("close output");

    assert_eq!(tokio::fs::read(path).await.expect("read output"), expected);
    assert!(!bad.requested_ranges().is_empty());
    assert!(!good.requested_ranges().is_empty());
}

#[tokio::test]
async fn rejects_servers_that_ignore_range_requests() {
    let server = FaultServer::spawn(payload(4096), Behavior::IgnoreRange).await;
    let result = server
        .source(4096)
        .open(haya::ByteRange::new(0, 1024).expect("range"))
        .await;

    assert!(matches!(
        result,
        Err(error) if error.kind == SourceErrorKind::Protocol
    ));
}

#[tokio::test]
async fn rejects_a_conflicting_content_range_total() {
    let server = FaultServer::spawn(payload(4096), Behavior::Normal).await;
    let result = server
        .source(8192)
        .open(haya::ByteRange::new(0, 1024).expect("range"))
        .await;

    assert!(matches!(
        result,
        Err(error) if error.kind == SourceErrorKind::Protocol
    ));
}

#[tokio::test]
async fn rejects_encoded_ranges_when_reqwest_decoders_are_available() {
    let server = FaultServer::spawn(vec![0; 1024], Behavior::GzipEncoding).await;
    let client = Client::builder()
        .no_gzip()
        .no_brotli()
        .no_deflate()
        .no_zstd()
        .build()
        .expect("range client");
    let source = HttpRangeSource::new(client, server.url.clone(), HeaderMap::new(), 1024);

    let result = source
        .open(haya::ByteRange::new(0, 1024).expect("range"))
        .await;

    assert!(matches!(
        result,
        Err(error) if error.kind == SourceErrorKind::Protocol
    ));
}

#[tokio::test]
async fn redacts_the_url_from_transport_errors() {
    let server = FaultServer::spawn(payload(4096), Behavior::Disconnect).await;
    let mut url = server.url.clone();
    url.set_query(Some("token=secret"));
    let source = HttpRangeSource::new(Client::new(), url, HeaderMap::new(), 4096);
    let error = match source
        .open(haya::ByteRange::new(0, 1024).expect("range"))
        .await
    {
        Ok(_) => panic!("disconnected response must fail"),
        Err(error) => error,
    };

    assert!(!error.message.contains("secret"));
    assert!(!error.message.contains(server.url.as_str()));
}
