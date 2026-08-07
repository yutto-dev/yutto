use std::{
    collections::HashMap,
    sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
    },
    time::Duration,
};

use async_trait::async_trait;
use bytes::Bytes;
use futures_util::stream;
use haya::{
    ByteRange, ByteStream, CommitSink, DownloadError, DownloadSnapshot, DownloadSpec, Downloader,
    ProgressSink, RangeSource, SinkError, SourceError, SourceErrorKind,
};
use tokio_util::sync::CancellationToken;

#[derive(Default)]
struct MemorySink {
    bytes: Mutex<Vec<u8>>,
    flushes: AtomicUsize,
    closes: AtomicUsize,
}

impl MemorySink {
    fn with_bytes(bytes: &[u8]) -> Self {
        Self {
            bytes: Mutex::new(bytes.to_vec()),
            ..Self::default()
        }
    }

    fn bytes(&self) -> Vec<u8> {
        self.bytes.lock().expect("sink lock poisoned").clone()
    }
}

#[async_trait]
impl CommitSink for MemorySink {
    async fn committed_offset(&self) -> Result<u64, SinkError> {
        Ok(self.bytes.lock().expect("sink lock poisoned").len() as u64)
    }

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError> {
        let mut bytes = self.bytes.lock().expect("sink lock poisoned");
        if bytes.len() as u64 != offset {
            return Err(SinkError::new(format!(
                "append at {offset}, committed offset is {}",
                bytes.len()
            )));
        }
        bytes.extend_from_slice(&data);
        Ok(())
    }

    async fn flush(&self) -> Result<(), SinkError> {
        self.flushes.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    async fn close(&self) -> Result<(), SinkError> {
        self.closes.fetch_add(1, Ordering::Relaxed);
        self.flush().await
    }
}

struct MemorySource {
    payload: Bytes,
    failures: Mutex<HashMap<u64, usize>>,
    failure_kinds: HashMap<u64, SourceErrorKind>,
    fail_above: Option<u64>,
    delays: HashMap<u64, Duration>,
    requests: Mutex<Vec<ByteRange>>,
    pending: bool,
    pending_stream: bool,
    extra_byte: bool,
}

impl MemorySource {
    fn new(payload: Bytes) -> Self {
        Self {
            payload,
            failures: Mutex::new(HashMap::new()),
            failure_kinds: HashMap::new(),
            fail_above: None,
            delays: HashMap::new(),
            requests: Mutex::new(Vec::new()),
            pending: false,
            pending_stream: false,
            extra_byte: false,
        }
    }

    fn requests(&self) -> Vec<ByteRange> {
        self.requests.lock().expect("request lock poisoned").clone()
    }
}

#[async_trait]
impl RangeSource for MemorySource {
    async fn open(&self, range: ByteRange) -> Result<ByteStream, SourceError> {
        self.requests
            .lock()
            .expect("request lock poisoned")
            .push(range);
        if self.pending {
            std::future::pending::<()>().await;
        }
        if let Some(delay) = self.delays.get(&range.start) {
            tokio::time::sleep(*delay).await;
        }
        if let Some(remaining) = self
            .failures
            .lock()
            .expect("failure lock poisoned")
            .get_mut(&range.start)
        {
            if *remaining > 0 {
                *remaining -= 1;
                return Err(SourceError::new(
                    self.failure_kinds
                        .get(&range.start)
                        .copied()
                        .unwrap_or(SourceErrorKind::Timeout),
                    "injected source failure",
                ));
            }
        }
        if self.fail_above.is_some_and(|limit| range.length() > limit) {
            return Err(SourceError::new(
                SourceErrorKind::Timeout,
                "range is deliberately too large",
            ));
        }
        if self.pending_stream {
            return Ok(Box::pin(stream::pending()));
        }

        let start = range.start.min(self.payload.len() as u64) as usize;
        let end = range.end.min(self.payload.len() as u64) as usize;
        let mut bytes = self.payload.slice(start..end).to_vec();
        if self.extra_byte {
            bytes.push(0xff);
        }
        let chunks = bytes
            .chunks(7 * 1024)
            .map(|chunk| Ok(Bytes::copy_from_slice(chunk)))
            .collect::<Vec<_>>();
        Ok(Box::pin(stream::iter(chunks)))
    }
}

#[derive(Default)]
struct RecordedProgress {
    snapshots: Mutex<Vec<DownloadSnapshot>>,
}

impl ProgressSink for RecordedProgress {
    fn update(&self, snapshot: DownloadSnapshot) {
        self.snapshots
            .lock()
            .expect("progress lock poisoned")
            .push(snapshot);
    }
}

fn payload(size: usize) -> Bytes {
    Bytes::from(
        (0..size)
            .map(|index| (index % 251) as u8)
            .collect::<Vec<_>>(),
    )
}

fn spec(expected_size: u64, page_size: usize) -> DownloadSpec {
    DownloadSpec {
        expected_size,
        page_size,
        block_size: page_size * 2,
        window_pages: 4,
        workers: 3,
        max_attempts: 3,
        source_cooldown: Duration::from_millis(1),
        attempt_timeout: Duration::from_secs(1),
    }
}

async fn assert_pending_attempt_times_out(source: MemorySource) {
    let mut download_spec = spec(1024, 1024);
    download_spec.workers = 1;
    download_spec.max_attempts = 1;
    download_spec.attempt_timeout = Duration::from_millis(10);

    let result = Downloader::new(
        download_spec,
        vec![Arc::new(source)],
        Arc::new(MemorySink::default()),
    )
    .expect("valid downloader")
    .run()
    .await;

    assert!(matches!(
        result,
        Err(DownloadError::RetryExhausted { last_error, .. })
            if last_error.kind == SourceErrorKind::Timeout
    ));
}

#[tokio::test]
async fn times_out_a_pending_source_open() {
    let mut source = MemorySource::new(payload(1024));
    source.pending = true;

    assert_pending_attempt_times_out(source).await;
}

#[tokio::test]
async fn times_out_a_pending_response_body() {
    let mut source = MemorySource::new(payload(1024));
    source.pending_stream = true;

    assert_pending_attempt_times_out(source).await;
}

#[tokio::test]
async fn downloads_out_of_order_ranges_and_a_short_final_page() {
    let expected = payload(10 * 1024 + 17);
    let mut source = MemorySource::new(expected.clone());
    source.delays.insert(0, Duration::from_millis(30));
    let sink = Arc::new(MemorySink::default());

    let report = Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![Arc::new(source)],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("download succeeds");

    assert_eq!(sink.bytes(), expected);
    assert_eq!(report.committed_bytes, expected.len() as u64);
    assert_eq!(report.received_bytes, expected.len() as u64);
    assert_eq!(sink.closes.load(Ordering::Relaxed), 1);
}

#[tokio::test]
async fn switches_sources_after_a_failure() {
    let expected = payload(8 * 1024);
    let mut failing = MemorySource::new(expected.clone());
    failing.fail_above = Some(0);
    let failing = Arc::new(failing);
    let healthy = Arc::new(MemorySource::new(expected.clone()));
    let sink = Arc::new(MemorySink::default());

    Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![failing.clone(), healthy.clone()],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("healthy source completes the download");

    assert_eq!(sink.bytes(), expected);
    assert!(!failing.requests().is_empty());
    assert!(!healthy.requests().is_empty());
}

#[tokio::test]
async fn waits_for_a_failed_source_cooldown() {
    let expected = payload(4 * 1024);
    let mut source = MemorySource::new(expected.clone());
    source.failures.get_mut().expect("failure map").insert(0, 1);
    let source = Arc::new(source);
    let sink = Arc::new(MemorySink::default());
    let mut download_spec = spec(expected.len() as u64, 1024);
    download_spec.workers = 1;
    download_spec.source_cooldown = Duration::from_millis(10);

    Downloader::new(download_spec, vec![source.clone()], sink.clone())
        .expect("valid downloader")
        .run()
        .await
        .expect("source recovers after cooldown");

    assert_eq!(sink.bytes(), expected);
    assert_eq!(
        source
            .requests()
            .iter()
            .filter(|range| range.start == 0)
            .count(),
        2
    );
}

#[tokio::test]
async fn disables_a_source_after_a_protocol_failure() {
    let expected = payload(8 * 1024);
    let mut bad = MemorySource::new(expected.clone());
    bad.failures.get_mut().expect("failure map").insert(0, 1);
    bad.failure_kinds.insert(0, SourceErrorKind::Protocol);
    let bad = Arc::new(bad);
    let healthy = Arc::new(MemorySource::new(expected.clone()));
    let sink = Arc::new(MemorySink::default());

    Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![bad.clone(), healthy.clone()],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("healthy source replaces the rejected source");

    assert_eq!(sink.bytes(), expected);
    assert!(!healthy.requests().is_empty());
}

#[tokio::test]
async fn bounds_started_requests_to_the_fixed_window() {
    let expected = payload(16 * 1024);
    let mut source = MemorySource::new(expected.clone());
    source.delays.insert(0, Duration::from_millis(50));
    let source = Arc::new(source);
    let sink = Arc::new(MemorySink::default());
    let progress = Arc::new(RecordedProgress::default());
    let downloader = Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![source.clone()],
        sink.clone(),
    )
    .expect("valid downloader")
    .with_progress_sink(progress.clone());

    let task = tokio::spawn(downloader.run());
    tokio::time::sleep(Duration::from_millis(10)).await;
    assert!(source.requests().iter().all(|range| range.end <= 4 * 1024));
    task.await
        .expect("download task joins")
        .expect("download succeeds");

    assert_eq!(sink.bytes(), expected);
    assert!(
        progress
            .snapshots
            .lock()
            .expect("progress lock poisoned")
            .iter()
            .any(|snapshot| snapshot.window_saturated)
    );
}

#[tokio::test]
async fn caps_large_blocks_to_the_fixed_window() {
    let expected = payload(16 * 1024);
    let source = Arc::new(MemorySource::new(expected.clone()));
    let sink = Arc::new(MemorySink::default());
    let mut download_spec = spec(expected.len() as u64, 1024);
    download_spec.block_size = 64 * 1024;
    download_spec.workers = 1;

    Downloader::new(download_spec, vec![source.clone()], sink.clone())
        .expect("valid downloader")
        .run()
        .await
        .expect("download succeeds");

    assert_eq!(sink.bytes(), expected);
    assert!(
        source
            .requests()
            .iter()
            .all(|range| range.length() <= 4 * 1024)
    );
}

#[tokio::test]
async fn splits_repeatedly_failing_blocks_down_to_pages() {
    let expected = payload(9 * 1024);
    let mut source = MemorySource::new(expected.clone());
    source.fail_above = Some(1024);
    let source = Arc::new(source);
    let sink = Arc::new(MemorySink::default());
    let mut download_spec = spec(expected.len() as u64, 1024);
    download_spec.block_size = 4 * 1024;
    download_spec.max_attempts = 1;

    Downloader::new(download_spec, vec![source.clone()], sink.clone())
        .expect("valid downloader")
        .run()
        .await
        .expect("split pages succeed");

    assert_eq!(sink.bytes(), expected);
    assert!(
        source
            .requests()
            .iter()
            .any(|range| range.length() == 4 * 1024)
    );
    assert!(source.requests().iter().any(|range| range.length() == 1024));
}

#[tokio::test]
async fn resumes_from_the_committed_prefix() {
    let expected = payload(8 * 1024 + 7);
    let prefix = 1237;
    let source = Arc::new(MemorySource::new(expected.clone()));
    let sink = Arc::new(MemorySink::with_bytes(&expected[..prefix]));

    let report = Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![source.clone()],
        sink.clone(),
    )
    .expect("valid downloader")
    .run()
    .await
    .expect("resume succeeds");

    assert_eq!(sink.bytes(), expected);
    assert_eq!(source.requests()[0].start, prefix as u64);
    assert_eq!(report.received_bytes, (expected.len() - prefix) as u64);
}

#[tokio::test]
async fn completes_an_already_finished_download_without_sources() {
    let expected = payload(3);
    let sink = Arc::new(MemorySink::with_bytes(&expected));

    let report = Downloader::new(spec(expected.len() as u64, 1024), vec![], sink.clone())
        .expect("valid downloader")
        .run()
        .await
        .expect("complete sink needs no source");

    assert_eq!(report.committed_bytes, expected.len() as u64);
    assert_eq!(report.received_bytes, 0);
    assert_eq!(report.attempts, 0);
}

#[tokio::test]
async fn rejects_an_incomplete_download_without_sources() {
    let result = Downloader::new(spec(3, 1024), vec![], Arc::new(MemorySink::default()))
        .expect("valid downloader")
        .run()
        .await;

    assert!(matches!(result, Err(DownloadError::NoUsableSource)));
}

#[tokio::test]
async fn rejects_an_oversized_sink() {
    let source = Arc::new(MemorySource::new(payload(3)));
    let sink = Arc::new(MemorySink::with_bytes(&[0; 4]));

    let result = Downloader::new(spec(3, 1024), vec![source.clone()], sink)
        .expect("valid downloader")
        .run()
        .await;

    assert!(matches!(result, Err(DownloadError::InvalidSpec(_))));
    assert!(source.requests().is_empty());
}

#[tokio::test]
async fn rejects_oversized_range_responses() {
    let expected = payload(4 * 1024);
    let mut source = MemorySource::new(expected);
    source.extra_byte = true;
    let result = Downloader::new(
        spec(4 * 1024, 1024),
        vec![Arc::new(source)],
        Arc::new(MemorySink::default()),
    )
    .expect("valid downloader")
    .run()
    .await;

    assert!(matches!(
        result,
        Err(DownloadError::RetryExhausted { last_error, .. })
            if last_error.kind == SourceErrorKind::Protocol
    ));
}

#[tokio::test]
async fn flushes_the_committed_prefix_before_retry_exhaustion() {
    let expected = payload(2 * 1024);
    let mut source = MemorySource::new(expected.clone());
    source
        .failures
        .get_mut()
        .expect("failure map")
        .insert(1024, 1);
    source.failure_kinds.insert(1024, SourceErrorKind::Protocol);
    let sink = Arc::new(MemorySink::default());
    let mut download_spec = spec(expected.len() as u64, 1024);
    download_spec.block_size = 1024;
    download_spec.workers = 1;
    download_spec.max_attempts = 1;

    let result = Downloader::new(download_spec, vec![Arc::new(source)], sink.clone())
        .expect("valid downloader")
        .run()
        .await;

    assert!(matches!(result, Err(DownloadError::RetryExhausted { .. })));
    assert_eq!(sink.bytes(), expected.slice(..1024));
    assert_eq!(sink.flushes.load(Ordering::Relaxed), 1);
    assert_eq!(sink.closes.load(Ordering::Relaxed), 0);
}

#[tokio::test]
async fn cancellation_flushes_the_sink() {
    let expected = payload(4 * 1024);
    let mut source = MemorySource::new(expected.clone());
    source.pending = true;
    let cancellation = CancellationToken::new();
    let sink = Arc::new(MemorySink::default());
    let downloader = Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![Arc::new(source)],
        sink.clone(),
    )
    .expect("valid downloader")
    .with_cancellation_token(cancellation.clone());

    let task = tokio::spawn(downloader.run());
    tokio::time::sleep(Duration::from_millis(10)).await;
    cancellation.cancel();

    assert!(matches!(
        task.await.expect("task joins"),
        Err(DownloadError::Cancelled)
    ));
    assert_eq!(sink.flushes.load(Ordering::Relaxed), 1);
    assert_eq!(sink.closes.load(Ordering::Relaxed), 0);
}

#[tokio::test]
async fn cancellation_wins_over_an_immediately_ready_final_block() {
    let expected = payload(1024);
    let cancellation = CancellationToken::new();
    cancellation.cancel();
    let sink = Arc::new(MemorySink::default());

    let result = Downloader::new(
        spec(expected.len() as u64, 1024),
        vec![Arc::new(MemorySource::new(expected))],
        sink.clone(),
    )
    .expect("valid downloader")
    .with_cancellation_token(cancellation)
    .run()
    .await;

    assert!(matches!(result, Err(DownloadError::Cancelled)));
    assert!(sink.bytes().is_empty());
    assert_eq!(sink.flushes.load(Ordering::Relaxed), 1);
    assert_eq!(sink.closes.load(Ordering::Relaxed), 0);
}
