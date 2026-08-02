use async_trait::async_trait;
use futures_util::StreamExt;
use haya::{ByteRange, ByteStream, RangeSource, SourceError, SourceErrorKind};
use reqwest::{
    Client, Request, StatusCode, Url,
    header::{ACCEPT_ENCODING, CONTENT_RANGE, HeaderMap, HeaderValue, IF_RANGE, RANGE},
};

pub struct HttpRangeSource {
    client: Client,
    url: Url,
    headers: HeaderMap,
}

impl HttpRangeSource {
    pub fn new(client: Client, url: Url, headers: HeaderMap) -> Self {
        Self {
            client,
            url,
            headers,
        }
    }

    fn request(&self, range: ByteRange) -> Result<Request, SourceError> {
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
        request.headers_mut().remove(IF_RANGE);
        Ok(request)
    }
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
    let value = headers
        .get(CONTENT_RANGE)
        .ok_or_else(|| {
            SourceError::new(SourceErrorKind::Protocol, "response has no Content-Range")
        })?
        .to_str()
        .map_err(|error| {
            SourceError::new(
                SourceErrorKind::Protocol,
                format!("Content-Range is not valid ASCII: {error}"),
            )
        })?;
    let value = value.strip_prefix("bytes ").ok_or_else(|| {
        SourceError::new(
            SourceErrorKind::Protocol,
            format!("unsupported Content-Range unit: {value}"),
        )
    })?;
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
    SourceError::new(kind, error.to_string())
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
    use reqwest::{
        Client, Url,
        header::{ACCEPT_ENCODING, CONTENT_RANGE, HeaderMap, IF_RANGE, RANGE},
    };

    use super::{HttpRangeSource, satisfied_content_range};
    use haya::ByteRange;

    #[test]
    fn range_requests_replace_conflicting_headers() {
        let mut default_headers = HeaderMap::new();
        default_headers.append(ACCEPT_ENCODING, "gzip".parse().expect("header"));
        default_headers.append(RANGE, "bytes=7-".parse().expect("header"));
        default_headers.append(IF_RANGE, "stale-default".parse().expect("header"));
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
    fn parses_satisfied_content_ranges() {
        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_RANGE, "bytes 2-5/9".parse().expect("header"));
        let parsed = satisfied_content_range(&headers).expect("valid range");
        assert_eq!((parsed.start, parsed.end, parsed.total), (2, 5, Some(9)));
    }
}
