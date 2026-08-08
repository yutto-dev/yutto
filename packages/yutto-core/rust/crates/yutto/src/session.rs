use std::{
    collections::{BTreeMap, HashMap},
    sync::{Arc, Mutex},
    time::Duration,
};

use bytes::Bytes;
use reqwest::{
    Client, Proxy, StatusCode, Url,
    cookie::{CookieStore, Jar},
    header::{HeaderMap, HeaderName, HeaderValue},
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

        let default_headers = build_headers(config.headers)?;
        let cookies = Arc::new(SessionCookieStore::new(config.cookies)?);
        let mut builder = Client::builder()
            .no_gzip()
            .no_brotli()
            .no_deflate()
            .no_zstd()
            .default_headers(default_headers)
            .cookie_provider(cookies.clone())
            .danger_accept_invalid_certs(config.accept_invalid_certs)
            .read_timeout(config.read_timeout)
            .connect_timeout(config.connect_timeout);
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
    use std::{collections::HashMap, time::Duration};

    use reqwest::{Url, cookie::CookieStore, header::HeaderValue};
    use tokio::{
        io::{AsyncReadExt, AsyncWriteExt},
        net::TcpListener,
        sync::oneshot,
    };

    use super::{Session, SessionConfig, SessionCookieStore, SessionError};

    async fn serve_once(
        response: &'static str,
        delay: Duration,
    ) -> (String, oneshot::Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("listener");
        let address = listener.local_addr().expect("address");
        let (request_sender, request_receiver) = oneshot::channel();
        tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.expect("connection");
            let mut request = vec![0; 8192];
            let length = stream.read(&mut request).await.expect("request");
            let _ = request_sender.send(String::from_utf8_lossy(&request[..length]).into_owned());
            tokio::time::sleep(delay).await;
            let _ = stream.write_all(response.as_bytes()).await;
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
        assert!(request.contains("cookie: token=initial\r\n"));
        assert_eq!(
            session.cookie("token", &url).expect("cookie"),
            Some("updated".into())
        );
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
