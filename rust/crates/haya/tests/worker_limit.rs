use std::{
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
    ByteRange, ByteStream, CommitSink, DownloadSpec, Downloader, RangeSource, SinkError,
    SourceError, WorkerLimit,
};
use tokio::sync::Notify;
use tokio_util::sync::CancellationToken;

#[derive(Default)]
struct MemorySink(Mutex<Vec<u8>>);

#[async_trait]
impl CommitSink for MemorySink {
    async fn committed_offset(&self) -> Result<u64, SinkError> {
        Ok(self.0.lock().expect("sink lock poisoned").len() as u64)
    }

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError> {
        let mut bytes = self.0.lock().expect("sink lock poisoned");
        if bytes.len() as u64 != offset {
            return Err(SinkError::new("non-contiguous append"));
        }
        bytes.extend_from_slice(&data);
        Ok(())
    }

    async fn flush(&self) -> Result<(), SinkError> {
        Ok(())
    }
}

#[derive(Default)]
struct Activity {
    active: AtomicUsize,
    peak: AtomicUsize,
    total: AtomicUsize,
    changed: Notify,
}

impl Activity {
    fn enter(self: &Arc<Self>) -> ActivityGuard {
        let active = self.active.fetch_add(1, Ordering::SeqCst) + 1;
        self.total.fetch_add(1, Ordering::SeqCst);
        self.peak.fetch_max(active, Ordering::SeqCst);
        self.changed.notify_waiters();
        ActivityGuard(self.clone())
    }

    async fn wait_for_total(&self, expected: usize) {
        loop {
            let notified = self.changed.notified();
            if self.total.load(Ordering::SeqCst) >= expected {
                return;
            }
            notified.await;
        }
    }
}

struct ActivityGuard(Arc<Activity>);

impl Drop for ActivityGuard {
    fn drop(&mut self) {
        self.0.active.fetch_sub(1, Ordering::SeqCst);
        self.0.changed.notify_waiters();
    }
}

struct TrackedSource {
    payload: Bytes,
    activity: Arc<Activity>,
    release: Arc<Notify>,
}

#[async_trait]
impl RangeSource for TrackedSource {
    async fn open(&self, range: ByteRange) -> Result<ByteStream, SourceError> {
        let guard = self.activity.enter();
        self.release.notified().await;
        let bytes = self.payload.slice(range.start as usize..range.end as usize);
        Ok(Box::pin(stream::once(async move {
            drop(guard);
            Ok(bytes)
        })))
    }
}

fn spec(size: usize, workers: usize) -> DownloadSpec {
    let mut spec = DownloadSpec::new(size as u64);
    spec.page_size = 1024;
    spec.block_size = 1024;
    spec.window_pages = 16;
    spec.workers = workers;
    spec.attempt_timeout = Duration::from_secs(2);
    spec
}

#[test]
fn rejects_a_zero_capacity() {
    assert!(WorkerLimit::new(0).is_err());
    assert!(WorkerLimit::new(tokio::sync::Semaphore::MAX_PERMITS + 1).is_err());
}

#[tokio::test]
async fn bounds_two_downloaders_and_reuses_released_workers() {
    let activity = Arc::new(Activity::default());
    let release = Arc::new(Notify::new());
    let limit = WorkerLimit::new(3).expect("valid limit");
    let payload = Bytes::from(vec![7; 8 * 1024]);
    let source = Arc::new(TrackedSource {
        payload: payload.clone(),
        activity: activity.clone(),
        release: release.clone(),
    });

    let first = tokio::spawn(
        Downloader::new(
            spec(payload.len(), 8),
            vec![source.clone()],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit.clone())
        .run(),
    );
    let second = tokio::spawn(
        Downloader::new(
            spec(payload.len(), 8),
            vec![source],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit)
        .run(),
    );

    activity.wait_for_total(3).await;
    assert_eq!(activity.active.load(Ordering::SeqCst), 3);
    assert_eq!(activity.peak.load(Ordering::SeqCst), 3);

    release.notify_waiters();
    tokio::time::timeout(Duration::from_millis(500), activity.wait_for_total(4))
        .await
        .expect("a waiting sibling reuses a released worker");
    while !first.is_finished() || !second.is_finished() {
        release.notify_waiters();
        tokio::task::yield_now().await;
    }
    first.await.expect("first joins").expect("first succeeds");
    second
        .await
        .expect("second joins")
        .expect("second succeeds");
    assert_eq!(activity.peak.load(Ordering::SeqCst), 3);
}

#[tokio::test]
async fn waiting_for_a_worker_does_not_consume_attempt_timeout() {
    let activity = Arc::new(Activity::default());
    let first_release = Arc::new(Notify::new());
    let limit = WorkerLimit::new(1).expect("valid limit");
    let payload = Bytes::from(vec![3; 1024]);

    let mut first_spec = spec(payload.len(), 1);
    first_spec.attempt_timeout = Duration::from_secs(1);
    let first = tokio::spawn(
        Downloader::new(
            first_spec,
            vec![Arc::new(TrackedSource {
                payload: payload.clone(),
                activity: activity.clone(),
                release: first_release.clone(),
            })],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit.clone())
        .run(),
    );
    activity.wait_for_total(1).await;

    let second_release = Arc::new(Notify::new());
    let mut second_spec = spec(payload.len(), 1);
    second_spec.attempt_timeout = Duration::from_millis(20);
    let second = tokio::spawn(
        Downloader::new(
            second_spec,
            vec![Arc::new(TrackedSource {
                payload,
                activity: activity.clone(),
                release: second_release.clone(),
            })],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit)
        .run(),
    );

    tokio::time::sleep(Duration::from_millis(50)).await;
    assert!(!second.is_finished());
    first_release.notify_waiters();
    first.await.expect("first joins").expect("first succeeds");
    activity.wait_for_total(2).await;
    second_release.notify_waiters();
    second
        .await
        .expect("second joins")
        .expect("second succeeds");
}

#[tokio::test]
async fn cancelling_a_worker_waiter_does_not_leak_capacity() {
    let activity = Arc::new(Activity::default());
    let release = Arc::new(Notify::new());
    let limit = WorkerLimit::new(1).expect("valid limit");
    let payload = Bytes::from(vec![5; 1024]);
    let first = tokio::spawn(
        Downloader::new(
            spec(payload.len(), 1),
            vec![Arc::new(TrackedSource {
                payload: payload.clone(),
                activity: activity.clone(),
                release: release.clone(),
            })],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit.clone())
        .run(),
    );
    activity.wait_for_total(1).await;

    let cancellation = CancellationToken::new();
    let waiting = tokio::spawn(
        Downloader::new(
            spec(payload.len(), 1),
            vec![Arc::new(TrackedSource {
                payload: payload.clone(),
                activity: activity.clone(),
                release: release.clone(),
            })],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit.clone())
        .with_cancellation_token(cancellation.clone())
        .run(),
    );
    tokio::task::yield_now().await;
    cancellation.cancel();
    assert!(matches!(
        tokio::time::timeout(Duration::from_millis(100), waiting)
            .await
            .expect("waiter cancels promptly")
            .expect("waiter joins"),
        Err(haya::DownloadError::Cancelled)
    ));

    release.notify_waiters();
    first.await.expect("first joins").expect("first succeeds");

    let third_release = Arc::new(Notify::new());
    let third = tokio::spawn(
        Downloader::new(
            spec(payload.len(), 1),
            vec![Arc::new(TrackedSource {
                payload,
                activity: activity.clone(),
                release: third_release.clone(),
            })],
            Arc::new(MemorySink::default()),
        )
        .expect("valid downloader")
        .with_worker_limit(limit)
        .run(),
    );
    activity.wait_for_total(2).await;
    third_release.notify_waiters();
    third.await.expect("third joins").expect("third succeeds");
}
