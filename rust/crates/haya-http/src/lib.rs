use async_trait::async_trait;
use futures_util::StreamExt;
use haya::{ByteRange, ByteStream, RangeSource, SourceError, SourceErrorKind};
use reqwest::{
    Client, Request, StatusCode, Url,
    header::{
        ACCEPT_ENCODING, CONTENT_ENCODING, CONTENT_RANGE, HeaderMap, HeaderValue, IF_RANGE, RANGE,
    },
};

pub struct HttpRangeSource {
    client: Client,
    url: Url,
    headers: HeaderMap,
    expected_size: u64,
}

impl HttpRangeSource {
    /// Creates a source for one known-size resource.
    ///
    /// The client's default headers must not contain `If-Range`: reqwest adds
    /// missing default headers when executing a request, after this adapter has
    /// deliberately stripped any per-source `If-Range` value.
    ///
    /// The client must also be built with `no_gzip`, `no_brotli`, `no_deflate`,
    /// and `no_zstd`. Cargo feature unification can otherwise enable reqwest's
    /// automatic response decompression before this adapter validates the wire
    /// encoding.
    pub fn new(client: Client, url: Url, headers: HeaderMap, expected_size: u64) -> Self {
        Self {
            client,
            url,
            headers,
            expected_size,
        }
    }

    fn request(&self, range: ByteRange) -> Result<Request, SourceError> {
        if range.start >= range.end || range.end > self.expected_size {
            return Err(SourceError::new(
                SourceErrorKind::Protocol,
                format!(
                    "range {range:?} is outside resource size {}",
                    self.expected_size
                ),
            ));
        }
        let mut request = self
            .client
            .get(self.url.clone())
            .headers(self.headers.clone())
            .build()
            .map_err(classify_reqwest_error)?;
        request
            .headers_mut()
            .insert(ACCEPT_ENCODING, HeaderValue::from_static("identity"));
        request.headers_mut().insert(
            RANGE,
            HeaderValue::from_str(&format!("bytes={}-{}", range.start, range.end - 1)).map_err(
                |error| {
                    SourceError::new(
                        SourceErrorKind::Protocol,
                        format!("invalid generated Range header: {error}"),
                    )
                },
            )?,
        );
        // This removes per-source values. Client defaults are applied later by
        // reqwest and are therefore excluded by `new`'s documented precondition.
        request.headers_mut().remove(IF_RANGE);
        Ok(request)
    }
}

/// Probes the size of a media resource without consuming its response body.
///
/// A valid probe response is an identity-encoded `206` for bytes `0-1` with a
/// known total in `Content-Range`. Other HTTP responses are treated as an
/// unavailable size; request failures retain their source error.
/// The client must have reqwest's automatic response decompression disabled.
pub async fn probe_size(client: &Client, url: Url) -> Result<Option<u64>, SourceError> {
    let request = client
        .get(url)
        .header(ACCEPT_ENCODING, HeaderValue::from_static("identity"))
        .header(RANGE, HeaderValue::from_static("bytes=0-1"))
        .build()
        .map_err(classify_reqwest_error)?;
    let response = client
        .execute(request)
        .await
        .map_err(classify_reqwest_error)?;
    if response.status() != StatusCode::PARTIAL_CONTENT {
        return Ok(None);
    }
    Ok(size_from_probe_headers(response.headers()))
}

fn size_from_probe_headers(headers: &HeaderMap) -> Option<u64> {
    validate_content_encoding(headers).ok()?;
    let content_range = satisfied_content_range(headers).ok()?;
    if content_range.start != 0 || content_range.end != 1 {
        return None;
    }
    content_range.total
}

#[async_trait]
impl RangeSource for HttpRangeSource {
    async fn open(&self, range: ByteRange) -> Result<ByteStream, SourceError> {
        let response = self
            .client
            .execute(self.request(range)?)
            .await
            .map_err(classify_reqwest_error)?;
        if response.status() != StatusCode::PARTIAL_CONTENT {
            return Err(status_error(response.status()));
        }

        validate_content_encoding(response.headers())?;
        let content_range = satisfied_content_range(response.headers())?;
        if content_range.start != range.start || content_range.end.checked_add(1) != Some(range.end)
        {
            return Err(SourceError::new(
                SourceErrorKind::Protocol,
                format!(
                    "requested {range:?}, got Content-Range {}-{}/{}",
                    content_range.start,
                    content_range.end,
                    content_range
                        .total
                        .map_or_else(|| "*".into(), |total| total.to_string())
                ),
            ));
        }
        if let Some(total) = content_range
            .total
            .filter(|total| *total != self.expected_size)
        {
            return Err(SourceError::new(
                SourceErrorKind::Protocol,
                format!(
                    "expected resource size {}, got Content-Range total {}",
                    self.expected_size, total
                ),
            ));
        }

        Ok(Box::pin(
            response
                .bytes_stream()
                .map(|chunk| chunk.map_err(classify_reqwest_error)),
        ))
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct ContentRange {
    start: u64,
    end: u64,
    total: Option<u64>,
}

fn satisfied_content_range(headers: &HeaderMap) -> Result<ContentRange, SourceError> {
    let mut values = headers.get_all(CONTENT_RANGE).iter();
    let value = values.next().ok_or_else(|| {
        SourceError::new(SourceErrorKind::Protocol, "response has no Content-Range")
    })?;
    if values.next().is_some() {
        return Err(SourceError::new(
            SourceErrorKind::Protocol,
            "response has multiple Content-Range fields",
        ));
    }
    let value = value.to_str().map_err(|error| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("Content-Range is not valid ASCII: {error}"),
        )
    })?;
    let (unit, value) = value.split_once(' ').ok_or_else(|| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("unsupported Content-Range unit: {value}"),
        )
    })?;
    if !unit.eq_ignore_ascii_case("bytes") {
        return Err(SourceError::new(
            SourceErrorKind::Protocol,
            format!("unsupported Content-Range unit: {unit}"),
        ));
    }
    let value = value.trim_start();
    let (range, total) = value.split_once('/').ok_or_else(|| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("malformed Content-Range: {value}"),
        )
    })?;
    let (start, end) = range.split_once('-').ok_or_else(|| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("malformed Content-Range: {value}"),
        )
    })?;
    let start = parse_number(start, "Content-Range start")?;
    let end = parse_number(end, "Content-Range end")?;
    let total = (total != "*")
        .then(|| parse_number(total, "Content-Range total"))
        .transpose()?;
    if end < start || total.is_some_and(|total| end >= total) {
        return Err(SourceError::new(
            SourceErrorKind::Protocol,
            format!("invalid Content-Range bounds: {value}"),
        ));
    }
    Ok(ContentRange { start, end, total })
}

fn validate_content_encoding(headers: &HeaderMap) -> Result<(), SourceError> {
    for value in headers.get_all(CONTENT_ENCODING) {
        let value = value.to_str().map_err(|error| {
            SourceError::new(
                SourceErrorKind::Protocol,
                format!("Content-Encoding is not valid ASCII: {error}"),
            )
        })?;
        for coding in value.split(',').map(str::trim) {
            if !coding.eq_ignore_ascii_case("identity") {
                return Err(SourceError::new(
                    SourceErrorKind::Protocol,
                    format!("unsupported Content-Encoding: {coding}"),
                ));
            }
        }
    }
    Ok(())
}

fn parse_number(value: &str, field: &str) -> Result<u64, SourceError> {
    value.parse().map_err(|error| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("invalid {field} {value:?}: {error}"),
        )
    })
}

fn classify_reqwest_error(error: reqwest::Error) -> SourceError {
    let kind = if error.is_timeout() {
        SourceErrorKind::Timeout
    } else if error.is_connect() || error.is_body() {
        SourceErrorKind::Transport
    } else {
        SourceErrorKind::Other
    };
    SourceError::new(kind, error.without_url().to_string())
}

fn status_error(status: StatusCode) -> SourceError {
    let kind = if status.is_server_error()
        || status == StatusCode::REQUEST_TIMEOUT
        || status == StatusCode::TOO_MANY_REQUESTS
    {
        SourceErrorKind::Other
    } else {
        SourceErrorKind::Protocol
    };
    SourceError::new(kind, format!("expected HTTP 206, got {status}"))
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use reqwest::{
        Client, Url,
        header::{ACCEPT_ENCODING, CONTENT_ENCODING, CONTENT_RANGE, HeaderMap, IF_RANGE, RANGE},
    };
    use tokio::{
        io::{AsyncReadExt, AsyncWriteExt},
        net::TcpListener,
        sync::oneshot,
        time::timeout,
    };

    use super::{
        HttpRangeSource, probe_size, satisfied_content_range, size_from_probe_headers,
        validate_content_encoding,
    };
    use haya::ByteRange;

    fn install_rustls_provider() {
        let _ = rustls::crypto::ring::default_provider().install_default();
    }

    async fn serve_ignored_range_headers() -> (Url, oneshot::Receiver<String>, oneshot::Sender<()>)
    {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("listener");
        let address = listener.local_addr().expect("address");
        let (request_sender, request_receiver) = oneshot::channel();
        let (release_sender, release_receiver) = oneshot::channel();
        tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.expect("connection");
            let mut request = Vec::new();
            while !request.ends_with(b"\r\n\r\n") {
                let mut chunk = [0; 1024];
                let length = stream.read(&mut chunk).await.expect("request");
                if length == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..length]);
            }
            let _ = request_sender.send(String::from_utf8_lossy(&request).into_owned());
            stream
                .write_all(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 1000000000\r\nConnection: close\r\n\r\n",
                )
                .await
                .expect("response headers");
            let _ = release_receiver.await;
        });
        (
            Url::parse(&format!("http://{address}/media")).expect("URL"),
            request_receiver,
            release_sender,
        )
    }

    fn probe_client() -> Client {
        Client::builder()
            .no_gzip()
            .no_brotli()
            .no_deflate()
            .no_zstd()
            .build()
            .expect("client")
    }

    #[test]
    fn range_requests_replace_conflicting_headers() {
        install_rustls_provider();
        let mut default_headers = HeaderMap::new();
        default_headers.append(ACCEPT_ENCODING, "gzip".parse().expect("header"));
        default_headers.append(RANGE, "bytes=7-".parse().expect("header"));
        let client = Client::builder()
            .default_headers(default_headers)
            .build()
            .expect("client");
        let mut source_headers = HeaderMap::new();
        source_headers.append(ACCEPT_ENCODING, "br".parse().expect("header"));
        source_headers.append(RANGE, "bytes=9-".parse().expect("header"));
        source_headers.append(IF_RANGE, "stale-source".parse().expect("header"));
        let source = HttpRangeSource::new(
            client,
            Url::parse("https://example.test/media").expect("URL"),
            source_headers,
            9,
        );

        let request = source
            .request(ByteRange::new(2, 6).expect("range"))
            .expect("request");

        assert_eq!(
            request.headers().get(ACCEPT_ENCODING),
            Some(&"identity".parse().unwrap())
        );
        assert_eq!(
            request.headers().get(RANGE),
            Some(&"bytes=2-5".parse().unwrap())
        );
        assert!(request.headers().get(IF_RANGE).is_none());
    }

    #[test]
    fn rejects_ranges_outside_the_known_resource() {
        install_rustls_provider();
        let source = HttpRangeSource::new(
            Client::new(),
            Url::parse("https://example.test/media").expect("URL"),
            HeaderMap::new(),
            9,
        );

        assert!(source.request(ByteRange { start: 0, end: 0 }).is_err());
        assert!(source.request(ByteRange { start: 8, end: 10 }).is_err());
    }

    #[test]
    fn parses_satisfied_content_ranges() {
        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_RANGE, "bytes 2-5/9".parse().expect("header"));
        let parsed = satisfied_content_range(&headers).expect("valid range");
        assert_eq!((parsed.start, parsed.end, parsed.total), (2, 5, Some(9)));

        headers.insert(CONTENT_RANGE, "Bytes 2-5/9".parse().expect("header"));
        assert!(satisfied_content_range(&headers).is_ok());

        headers.append(CONTENT_RANGE, "bytes 2-5/9".parse().expect("header"));
        assert!(satisfied_content_range(&headers).is_err());
    }

    #[test]
    fn rejects_non_identity_content_encoding() {
        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_ENCODING, "gzip".parse().expect("header"));
        assert!(validate_content_encoding(&headers).is_err());

        headers.insert(CONTENT_ENCODING, "identity".parse().expect("header"));
        assert!(validate_content_encoding(&headers).is_ok());
    }

    #[test]
    fn size_probe_requires_the_requested_range_and_known_total() {
        let mut headers = HeaderMap::new();
        assert_eq!(size_from_probe_headers(&headers), None);

        headers.insert(CONTENT_RANGE, "bytes 0-1/9".parse().expect("header"));
        assert_eq!(size_from_probe_headers(&headers), Some(9));

        headers.insert(CONTENT_RANGE, "bytes 1-2/9".parse().expect("header"));
        assert_eq!(size_from_probe_headers(&headers), None);

        headers.insert(CONTENT_RANGE, "bytes 0-1/*".parse().expect("header"));
        assert_eq!(size_from_probe_headers(&headers), None);

        headers.insert(CONTENT_RANGE, "bytes 0-1/9".parse().expect("header"));
        headers.insert(CONTENT_ENCODING, "gzip".parse().expect("header"));
        assert_eq!(size_from_probe_headers(&headers), None);
    }

    #[tokio::test]
    async fn size_probe_drops_an_ignored_range_without_waiting_for_the_full_body() {
        install_rustls_provider();
        let (url, request, _held_body) = serve_ignored_range_headers().await;

        let size = timeout(Duration::from_secs(1), probe_size(&probe_client(), url))
            .await
            .expect("probe waited for the ignored full response body")
            .expect("probe request");
        let request = request.await.expect("captured request");

        assert_eq!(size, None);
        assert!(request.contains("range: bytes=0-1\r\n"));
        assert!(request.contains("accept-encoding: identity\r\n"));
    }
}
