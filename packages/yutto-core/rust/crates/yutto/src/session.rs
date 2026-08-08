use std::{
    collections::{BTreeMap, HashMap},
    fs,
    io::Read,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Duration,
};

use bytes::Bytes;
use flate2::read::{DeflateDecoder, GzDecoder, ZlibDecoder};
use reqwest::{
    Certificate, Client, ClientBuilder, Proxy, StatusCode, Url,
    cookie::{CookieStore, Jar},
    header::{ACCEPT_ENCODING, CONTENT_ENCODING, HeaderMap, HeaderName, HeaderValue},
};
use thiserror::Error;

const DEFAULT_READ_TIMEOUT: Duration = Duration::from_secs(5);
const DEFAULT_CONNECT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Error)]
pub enum SessionError {
    #[error("invalid URL: {0}")]
    InvalidUrl(String),
    #[error("unsupported URL protocol: {0}")]
    UnsupportedProtocol(String),
    #[error("HTTP request timed out: {0}")]
    Timeout(String),
    #[error("HTTP transport failed: {0}")]
    Transport(String),
    #[error("HTTP status {0}")]
    Status(u16),
    #[error("HTTP session is closed")]
    Closed,
    #[error("invalid HTTP configuration: {0}")]
    Configuration(String),
}

pub struct SessionConfig {
    pub headers: HashMap<String, String>,
    pub cookies: HashMap<String, String>,
    pub proxy: Option<String>,
    pub use_system_proxy: bool,
    pub accept_invalid_certs: bool,
    pub ca_cert_file: Option<PathBuf>,
    pub ca_cert_dir: Option<PathBuf>,
    pub read_timeout: Duration,
    pub connect_timeout: Duration,
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            headers: HashMap::new(),
            cookies: HashMap::new(),
            proxy: None,
            use_system_proxy: true,
            accept_invalid_certs: false,
            ca_cert_file: None,
            ca_cert_dir: None,
            read_timeout: DEFAULT_READ_TIMEOUT,
            connect_timeout: DEFAULT_CONNECT_TIMEOUT,
        }
    }
}

#[derive(Clone)]
pub struct Session {
    inner: Arc<SessionInner>,
}

struct SessionInner {
    client: Mutex<Option<Client>>,
    cookies: Arc<SessionCookieStore>,
}

pub struct Response {
    pub status: StatusCode,
    pub url: Url,
    pub headers: HeaderMap,
    pub body: Bytes,
}

impl Response {
    pub fn is_success(&self) -> bool {
        self.status.is_success()
    }

    pub fn header(&self, name: &str) -> Result<Option<&str>, SessionError> {
        let name = HeaderName::from_bytes(name.as_bytes())
            .map_err(|error| SessionError::Configuration(error.to_string()))?;
        self.headers
            .get(name)
            .map(|value| {
                value
                    .to_str()
                    .map_err(|error| SessionError::Configuration(error.to_string()))
            })
            .transpose()
    }

    pub fn error_for_status(&self) -> Result<(), SessionError> {
        if self.is_success() {
            Ok(())
        } else {
            Err(SessionError::Status(self.status.as_u16()))
        }
    }
}

impl Session {
    pub fn new(config: SessionConfig) -> Result<Self, SessionError> {
        if config.read_timeout.is_zero() {
            return Err(SessionError::Configuration(
                "read_timeout must be positive".into(),
            ));
        }
        if config.connect_timeout.is_zero() {
            return Err(SessionError::Configuration(
                "connect_timeout must be positive".into(),
            ));
        }

        let mut default_headers = build_headers(config.headers)?;
        default_headers
            .entry(ACCEPT_ENCODING)
            .or_insert(HeaderValue::from_static("gzip, deflate"));
        let cookies = Arc::new(SessionCookieStore::new(config.cookies)?);
        let mut builder = Client::builder()
            .no_gzip()
            .no_brotli()
            .no_deflate()
            .no_zstd()
            .referer(false)
            .default_headers(default_headers)
            .cookie_provider(cookies.clone())
            .danger_accept_invalid_certs(config.accept_invalid_certs)
            .read_timeout(config.read_timeout)
            .connect_timeout(config.connect_timeout);
        if let Some(path) = config.ca_cert_file {
            builder = add_root_certificates(builder, &path, true)?;
        } else if let Some(path) = config.ca_cert_dir {
            let entries = fs::read_dir(&path).map_err(|error| {
                SessionError::Configuration(format!(
                    "failed to read CA certificate directory {}: {error}",
                    path.display()
                ))
            })?;
            for entry in entries.flatten() {
                if entry.path().is_file() {
                    builder = add_root_certificates(builder, &entry.path(), false)?;
                }
            }
        }
        if !config.use_system_proxy {
            builder = builder.no_proxy();
        }
        if let Some(proxy) = config.proxy {
            builder = builder.proxy(
                Proxy::all(&proxy)
                    .map_err(|error| SessionError::Configuration(error.to_string()))?,
            );
        }
        let client = builder
            .build()
            .map_err(|error| SessionError::Configuration(error.to_string()))?;

        Ok(Self {
            inner: Arc::new(SessionInner {
                client: Mutex::new(Some(client)),
                cookies,
            }),
        })
    }

    pub async fn get(
        &self,
        url: String,
        params: Vec<(String, String)>,
        headers: HashMap<String, String>,
    ) -> Result<Response, SessionError> {
        let url = parse_url(&url)?;
        let request = self
            .client()?
            .get(url)
            .query(&params)
            .headers(build_headers(headers)?);
        let response = request.send().await.map_err(classify_reqwest_error)?;
        let status = response.status();
        let url = response.url().clone();
        let headers = response.headers().clone();
        let body = response.bytes().await.map_err(classify_reqwest_error)?;
        let body = decode_response_body(&headers, body)?;
        Ok(Response {
            status,
            url,
            headers,
            body,
        })
    }

    pub fn cookie(&self, name: &str, url: &str) -> Result<Option<String>, SessionError> {
        let url = parse_url(url)?;
        let Some(header) = self.inner.cookies.cookies(&url) else {
            return Ok(None);
        };
        let header = header
            .to_str()
            .map_err(|error| SessionError::Configuration(error.to_string()))?;
        Ok(header.split(';').map(str::trim).find_map(|cookie| {
            let (cookie_name, value) = cookie.split_once('=')?;
            (cookie_name == name).then(|| value.to_owned())
        }))
    }

    pub fn close(&self) {
        self.inner
            .client
            .lock()
            .expect("session client lock poisoned")
            .take();
    }

    pub fn is_closed(&self) -> bool {
        self.inner
            .client
            .lock()
            .expect("session client lock poisoned")
            .is_none()
    }

    pub(crate) fn client(&self) -> Result<Client, SessionError> {
        self.inner
            .client
            .lock()
            .expect("session client lock poisoned")
            .clone()
            .ok_or(SessionError::Closed)
    }
}

fn add_root_certificates(
    mut builder: ClientBuilder,
    path: &Path,
    required: bool,
) -> Result<ClientBuilder, SessionError> {
    let data = match fs::read(path) {
        Ok(data) => data,
        Err(_) if !required => return Ok(builder),
        Err(error) => {
            return Err(SessionError::Configuration(format!(
                "failed to read CA certificate file {}: {error}",
                path.display()
            )));
        }
    };
    let certificates = match Certificate::from_pem_bundle(&data) {
        Ok(certificates) if !certificates.is_empty() => certificates,
        Ok(_) | Err(_) if !required => return Ok(builder),
        Ok(_) => {
            return Err(SessionError::Configuration(format!(
                "CA certificate file {} contains no certificates",
                path.display()
            )));
        }
        Err(error) => {
            return Err(SessionError::Configuration(format!(
                "failed to parse CA certificate file {}: {error}",
                path.display()
            )));
        }
    };
    for certificate in certificates {
        builder = builder.add_root_certificate(certificate);
    }
    Ok(builder)
}

pub(crate) fn build_headers(headers: HashMap<String, String>) -> Result<HeaderMap, SessionError> {
    let mut result = HeaderMap::new();
    for (name, value) in headers {
        let header_name = HeaderName::from_bytes(name.as_bytes()).map_err(|error| {
            SessionError::Configuration(format!("invalid HTTP header name {name:?}: {error}"))
        })?;
        let header_value = HeaderValue::from_str(&value).map_err(|error| {
            SessionError::Configuration(format!("invalid HTTP header value: {error}"))
        })?;
        result.insert(header_name, header_value);
    }
    Ok(result)
}

fn parse_url(raw: &str) -> Result<Url, SessionError> {
    let url = Url::parse(raw).map_err(|error| SessionError::InvalidUrl(error.to_string()))?;
    if !matches!(url.scheme(), "http" | "https") {
        return Err(SessionError::UnsupportedProtocol(url.scheme().to_owned()));
    }
    Ok(url)
}

fn classify_reqwest_error(error: reqwest::Error) -> SessionError {
    let error = error.without_url();
    if error.is_timeout() {
        SessionError::Timeout(error.to_string())
    } else {
        SessionError::Transport(error.to_string())
    }
}

fn decode_response_body(headers: &HeaderMap, body: Bytes) -> Result<Bytes, SessionError> {
    let encodings = headers
        .get_all(CONTENT_ENCODING)
        .iter()
        .map(|encoding| {
            encoding.to_str().map_err(|error| {
                SessionError::Transport(format!("invalid Content-Encoding header: {error}"))
            })
        })
        .collect::<Result<Vec<_>, _>>()?;
    if encodings.is_empty() {
        return Ok(body);
    }
    let mut decoded = None;
    for encodings in encodings.into_iter().rev() {
        for encoding in encodings.split(',').rev().map(str::trim) {
            let input = decoded.as_deref().unwrap_or(body.as_ref());
            let next = if encoding.eq_ignore_ascii_case("gzip") {
                decode_reader(GzDecoder::new(input), "gzip")?
            } else if encoding.eq_ignore_ascii_case("deflate") {
                decode_deflate(input)?
            } else {
                continue;
            };
            decoded = Some(next);
        }
    }
    Ok(decoded.map_or(body, Bytes::from))
}

fn decode_deflate(body: &[u8]) -> Result<Vec<u8>, SessionError> {
    decode_reader(ZlibDecoder::new(body), "deflate")
        .or_else(|_| decode_reader(DeflateDecoder::new(body), "deflate"))
}

fn decode_reader(mut decoder: impl Read, encoding: &str) -> Result<Vec<u8>, SessionError> {
    let mut decoded = Vec::new();
    decoder.read_to_end(&mut decoded).map_err(|error| {
        SessionError::Transport(format!(
            "failed to decode {encoding} response body: {error}"
        ))
    })?;
    Ok(decoded)
}

#[derive(Debug)]
struct SessionCookieStore {
    jar: Jar,
    initial: BTreeMap<String, String>,
}

impl SessionCookieStore {
    fn new(initial: HashMap<String, String>) -> Result<Self, SessionError> {
        for (name, value) in &initial {
            HeaderValue::from_str(&format!("{name}={value}")).map_err(|error| {
                SessionError::Configuration(format!("invalid cookie {name:?}: {error}"))
            })?;
        }
        Ok(Self {
            jar: Jar::default(),
            initial: initial.into_iter().collect(),
        })
    }
}

impl CookieStore for SessionCookieStore {
    fn set_cookies(&self, cookie_headers: &mut dyn Iterator<Item = &HeaderValue>, url: &Url) {
        self.jar.set_cookies(cookie_headers, url);
    }

    fn cookies(&self, url: &Url) -> Option<HeaderValue> {
        let mut values = self.initial.clone();
        if let Some(header) = self.jar.cookies(url) {
            if let Ok(header) = header.to_str() {
                for cookie in header.split(';').map(str::trim) {
                    if let Some((name, value)) = cookie.split_once('=') {
                        values.insert(name.to_owned(), value.to_owned());
                    }
                }
            }
        }
        if values.is_empty() {
            None
        } else {
            HeaderValue::from_str(
                &values
                    .into_iter()
                    .map(|(name, value)| format!("{name}={value}"))
                    .collect::<Vec<_>>()
                    .join("; "),
            )
            .ok()
        }
    }
}

#[cfg(test)]
mod tests {
    use std::{collections::HashMap, io::Write, time::Duration};

    use flate2::{
        Compression,
        write::{DeflateEncoder, GzEncoder, ZlibEncoder},
    };
    use reqwest::{
        Url,
        cookie::CookieStore,
        header::{CONTENT_ENCODING, HeaderMap, HeaderValue},
    };
    use tokio::{
        io::{AsyncReadExt, AsyncWriteExt},
        net::TcpListener,
        sync::oneshot,
    };

    use super::{Session, SessionConfig, SessionCookieStore, SessionError, decode_response_body};

    async fn serve_once(
        response: impl AsRef<[u8]>,
        delay: Duration,
    ) -> (String, oneshot::Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("listener");
        let address = listener.local_addr().expect("address");
        let (request_sender, request_receiver) = oneshot::channel();
        let response = response.as_ref().to_vec();
        tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.expect("connection");
            let mut request = vec![0; 8192];
            let length = stream.read(&mut request).await.expect("request");
            let _ = request_sender.send(String::from_utf8_lossy(&request[..length]).into_owned());
            tokio::time::sleep(delay).await;
            let _ = stream.write_all(&response).await;
        });
        (format!("http://{address}/resource"), request_receiver)
    }

    async fn serve_streaming_body(interval: Duration) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("listener");
        let address = listener.local_addr().expect("address");
        tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.expect("connection");
            let mut request = vec![0; 8192];
            let _ = stream.read(&mut request).await.expect("request");
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\na")
                .await
                .expect("headers and first byte");
            tokio::time::sleep(interval).await;
            stream.write_all(b"b").await.expect("second byte");
            tokio::time::sleep(interval).await;
            stream.write_all(b"c").await.expect("third byte");
        });
        format!("http://{address}/resource")
    }

    async fn serve_redirect_once() -> (String, oneshot::Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("listener");
        let address = listener.local_addr().expect("address");
        let (request_sender, request_receiver) = oneshot::channel();
        tokio::spawn(async move {
            let (mut source, _) = listener.accept().await.expect("source connection");
            let mut request = vec![0; 8192];
            let _ = source.read(&mut request).await.expect("source request");
            source
                .write_all(
                    b"HTTP/1.1 302 Found\r\nLocation: /destination\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                )
                .await
                .expect("redirect response");

            let (mut destination, _) = listener.accept().await.expect("destination connection");
            let length = destination
                .read(&mut request)
                .await
                .expect("destination request");
            let _ = request_sender.send(String::from_utf8_lossy(&request[..length]).into_owned());
            destination
                .write_all(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\npayload",
                )
                .await
                .expect("destination response");
        });
        (
            format!("http://{address}/source?token=secret"),
            request_receiver,
        )
    }

    #[test]
    fn initial_cookies_are_available_across_hosts() {
        let store = SessionCookieStore::new(HashMap::from([("SESSDATA".into(), "secret".into())]))
            .expect("cookie store");

        for url in [
            "https://api.bilibili.com/x/web-interface/nav",
            "https://cdn.example.test/media.m4s",
        ] {
            assert_eq!(
                store.cookies(&Url::parse(url).expect("URL")),
                Some(HeaderValue::from_static("SESSDATA=secret"))
            );
        }
    }

    #[test]
    fn response_cookies_override_initial_values_for_their_host() {
        let store = SessionCookieStore::new(HashMap::from([("SESSDATA".into(), "old".into())]))
            .expect("cookie store");
        let url = Url::parse("https://www.bilibili.com/").expect("URL");
        let value = HeaderValue::from_static("SESSDATA=new; Domain=.bilibili.com; Path=/");
        store.set_cookies(&mut std::iter::once(&value), &url);

        assert_eq!(
            store.cookies(&url),
            Some(HeaderValue::from_static("SESSDATA=new"))
        );
        assert_eq!(
            store.cookies(&Url::parse("https://cdn.example.test/").expect("URL")),
            Some(HeaderValue::from_static("SESSDATA=old"))
        );
    }

    #[test]
    fn close_is_idempotent_and_rejects_new_clients() {
        let session = Session::new(SessionConfig::default()).expect("session");
        assert!(!session.is_closed());

        session.close();
        session.close();

        assert!(session.is_closed());
        assert!(matches!(session.client(), Err(SessionError::Closed)));
    }

    #[test]
    fn missing_custom_ca_paths_are_configuration_errors() {
        let path = std::env::temp_dir().join(format!("missing-yutto-ca-{}", std::process::id()));
        for config in [
            SessionConfig {
                ca_cert_file: Some(path.clone()),
                ..SessionConfig::default()
            },
            SessionConfig {
                ca_cert_dir: Some(path.clone()),
                ..SessionConfig::default()
            },
        ] {
            assert!(matches!(
                Session::new(config),
                Err(SessionError::Configuration(_))
            ));
        }
    }

    #[test]
    fn response_body_decodes_httpx_builtin_encodings() {
        let payload = b"<i><d>danmaku</d></i>";
        let mut gzip = GzEncoder::new(Vec::new(), Compression::default());
        gzip.write_all(payload).expect("gzip input");
        let mut zlib = ZlibEncoder::new(Vec::new(), Compression::default());
        zlib.write_all(payload).expect("zlib input");
        let mut deflate = DeflateEncoder::new(Vec::new(), Compression::default());
        deflate.write_all(payload).expect("deflate input");

        for (encoding, body) in [
            ("gzip", gzip.finish().expect("gzip body")),
            ("deflate", zlib.finish().expect("zlib body")),
            ("deflate", deflate.finish().expect("deflate body")),
        ] {
            let mut headers = HeaderMap::new();
            headers.insert(CONTENT_ENCODING, HeaderValue::from_static(encoding));

            assert_eq!(
                decode_response_body(&headers, body.into()).expect("decoded body"),
                payload.as_slice()
            );
        }
    }

    #[test]
    fn response_body_decodes_repeated_content_encoding_fields() {
        let payload = b"<i><d>danmaku</d></i>";
        let mut deflate = ZlibEncoder::new(Vec::new(), Compression::default());
        deflate.write_all(payload).expect("deflate input");
        let mut gzip = GzEncoder::new(Vec::new(), Compression::default());
        gzip.write_all(&deflate.finish().expect("deflate body"))
            .expect("gzip input");
        let mut headers = HeaderMap::new();
        headers.append(CONTENT_ENCODING, HeaderValue::from_static("deflate"));
        headers.append(CONTENT_ENCODING, HeaderValue::from_static("gzip"));

        assert_eq!(
            decode_response_body(&headers, gzip.finish().expect("gzip body").into())
                .expect("decoded body"),
            payload.as_slice()
        );
    }

    #[test]
    fn invalid_compressed_body_is_a_transport_error() {
        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_ENCODING, HeaderValue::from_static("gzip"));

        assert!(matches!(
            decode_response_body(&headers, b"not gzip".as_slice().into()),
            Err(SessionError::Transport(_))
        ));
    }

    #[tokio::test]
    async fn get_decodes_compressed_response_body() {
        let payload = b"<i><d>danmaku</d></i>";
        let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
        encoder.write_all(payload).expect("gzip input");
        let body = encoder.finish().expect("gzip body");
        let mut wire_response = format!(
            "HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            body.len()
        )
        .into_bytes();
        wire_response.extend(body);
        let (url, _) = serve_once(wire_response, Duration::ZERO).await;
        let session = Session::new(SessionConfig {
            use_system_proxy: false,
            ..SessionConfig::default()
        })
        .expect("session");

        let response = session
            .get(url, vec![], HashMap::new())
            .await
            .expect("response");

        assert_eq!(response.body, payload.as_slice());
        assert_eq!(
            response.header("content-encoding").expect("header"),
            Some("gzip")
        );
    }

    #[tokio::test]
    async fn get_returns_response_and_updates_the_shared_cookie_store() {
        let (url, request) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Length: 7\r\nX-Answer: 42\r\nSet-Cookie: token=updated; Path=/\r\nConnection: close\r\n\r\npayload",
            Duration::ZERO,
        )
        .await;
        let session = Session::new(SessionConfig {
            headers: HashMap::from([("X-Default".into(), "default".into())]),
            cookies: HashMap::from([("token".into(), "initial".into())]),
            use_system_proxy: false,
            ..SessionConfig::default()
        })
        .expect("session");

        let response = session
            .get(
                url.clone(),
                vec![("query".into(), "a b".into())],
                HashMap::from([("X-Request".into(), "request".into())]),
            )
            .await
            .expect("response");
        let request = request.await.expect("captured request");

        assert_eq!(response.status.as_u16(), 200);
        assert_eq!(response.body, "payload");
        assert_eq!(response.header("x-answer").expect("header"), Some("42"));
        assert!(request.starts_with("GET /resource?query=a+b HTTP/1.1\r\n"));
        assert!(request.contains("x-default: default\r\n"));
        assert!(request.contains("x-request: request\r\n"));
        assert!(request.contains("accept-encoding: gzip, deflate\r\n"));
        assert!(request.contains("cookie: token=initial\r\n"));
        assert_eq!(
            session.cookie("token", &url).expect("cookie"),
            Some("updated".into())
        );
    }

    #[tokio::test]
    async fn redirects_preserve_the_configured_referer() {
        let (url, redirected_request) = serve_redirect_once().await;
        let session = Session::new(SessionConfig {
            headers: HashMap::from([("Referer".into(), "https://www.bilibili.com".into())]),
            use_system_proxy: false,
            ..SessionConfig::default()
        })
        .expect("session");

        let response = session
            .get(url, vec![], HashMap::new())
            .await
            .expect("redirected response");
        let redirected_request = redirected_request.await.expect("redirected request");

        assert_eq!(response.body, "payload");
        assert!(redirected_request.contains("referer: https://www.bilibili.com\r\n"));
        assert!(!redirected_request.contains("token=secret"));
    }

    #[tokio::test]
    async fn get_classifies_read_timeouts() {
        let (url, _) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            Duration::from_secs(1),
        )
        .await;
        let session = Session::new(SessionConfig {
            use_system_proxy: false,
            read_timeout: Duration::from_millis(10),
            ..SessionConfig::default()
        })
        .expect("session");

        assert!(matches!(
            session.get(url, vec![], HashMap::new()).await,
            Err(SessionError::Timeout(_))
        ));
    }

    #[tokio::test]
    async fn read_timeout_resets_after_each_successful_read() {
        let url = serve_streaming_body(Duration::from_millis(600)).await;
        let session = Session::new(SessionConfig {
            use_system_proxy: false,
            read_timeout: Duration::from_secs(1),
            ..SessionConfig::default()
        })
        .expect("session");

        let response = session
            .get(url, vec![], HashMap::new())
            .await
            .expect("streaming response");

        assert_eq!(response.body, "abc");
    }
}
