use std::{collections::VecDeque, sync::Arc};

use bytes::{Bytes, BytesMut};
use futures_util::{FutureExt, StreamExt, future::BoxFuture, stream::FuturesUnordered};
use tokio::time::Instant;
use tokio_util::sync::CancellationToken;

use crate::{
    ByteRange, CommitSink, DownloadError, DownloadReport, DownloadSnapshot, DownloadSpec,
    NullProgressSink, ProgressSink, RangeSource, SourceError, SourceErrorKind,
    buffer::OrderedBuffer, sink::SharedSink, source::SharedSource, source_pool::SourcePool,
};

#[derive(Clone, Debug)]
struct WorkItem {
    range: ByteRange,
    attempts: usize,
}

struct AttemptResult {
    work: WorkItem,
    source: usize,
    result: Result<Bytes, SourceError>,
}

pub struct Downloader {
    spec: DownloadSpec,
    sources: Vec<SharedSource>,
    sink: SharedSink,
    progress: Arc<dyn ProgressSink>,
    cancellation: CancellationToken,
}

impl Downloader {
    pub fn new(
        spec: DownloadSpec,
        sources: Vec<Arc<dyn RangeSource>>,
        sink: Arc<dyn CommitSink>,
    ) -> Result<Self, DownloadError> {
        Ok(Self {
            spec: spec.validate()?,
            sources,
            sink,
            progress: Arc::new(NullProgressSink),
            cancellation: CancellationToken::new(),
        })
    }

    pub fn with_progress_sink(mut self, progress: Arc<dyn ProgressSink>) -> Self {
        self.progress = progress;
        self
    }

    pub fn with_cancellation_token(mut self, cancellation: CancellationToken) -> Self {
        self.cancellation = cancellation;
        self
    }

    pub async fn run(self) -> Result<DownloadReport, DownloadError> {
        if self.cancellation.is_cancelled() {
            return self.cancelled().await;
        }
        let committed = self.sink.committed_offset().await?;
        if committed > self.spec.expected_size {
            return Err(DownloadError::InvalidSpec(format!(
                "sink has {committed} committed bytes but resource size is {}",
                self.spec.expected_size
            )));
        }
        if committed == self.spec.expected_size {
            self.sink.close().await?;
            return Ok(DownloadReport {
                committed_bytes: committed,
                received_bytes: 0,
                attempts: 0,
            });
        }
        if self.sources.is_empty() {
            return self.fail_after_flush(DownloadError::NoUsableSource).await;
        }

        let pool = SourcePool::new(self.sources.clone(), self.spec.source_cooldown);
        self.run_bounded(pool, committed).await
    }

    async fn run_bounded(
        &self,
        mut pool: SourcePool,
        origin: u64,
    ) -> Result<DownloadReport, DownloadError> {
        let expected = self.spec.expected_size;
        let mut ring = OrderedBuffer::new(origin, self.spec.page_size, self.spec.window_pages)?;
        let mut queue = VecDeque::new();
        let mut in_flight: FuturesUnordered<BoxFuture<'static, AttemptResult>> =
            FuturesUnordered::new();
        let mut next_offset = origin;
        let mut furthest_started = origin;
        let mut committed = origin;
        let mut received = 0_u64;
        let mut attempts = 0_usize;

        loop {
            if self.cancellation.is_cancelled() {
                return self.cancelled().await;
            }
            self.enqueue_new_work(
                expected,
                ring.window_end_offset(),
                &mut next_offset,
                &mut queue,
                in_flight.len(),
            )?;

            while in_flight.len() < self.spec.workers {
                let Some(work) = queue.pop_front() else {
                    break;
                };
                let Some((source, range_source)) = pool.select(Instant::now()) else {
                    queue.push_front(work);
                    break;
                };
                attempts += 1;
                furthest_started = furthest_started.max(work.range.end);
                in_flight.push(
                    async move {
                        let result = fetch_exact(range_source, work.range).await;
                        AttemptResult {
                            work,
                            source,
                            result,
                        }
                    }
                    .boxed(),
                );
            }

            self.publish_progress(
                received,
                committed,
                &ring,
                next_offset,
                furthest_started,
                in_flight.len(),
            );

            if committed == expected {
                self.sink.close().await?;
                return Ok(DownloadReport {
                    committed_bytes: committed,
                    received_bytes: received,
                    attempts,
                });
            }

            if in_flight.is_empty() {
                if !pool.has_usable() {
                    return self.fail_after_flush(DownloadError::NoUsableSource).await;
                }
                if !queue.is_empty() {
                    let ready_at = pool.next_ready_at().ok_or(DownloadError::NoUsableSource)?;
                    tokio::select! {
                        biased;
                        _ = self.cancellation.cancelled() => return self.cancelled().await,
                        _ = tokio::time::sleep_until(ready_at) => continue,
                    }
                }
                return self.fail_after_flush(DownloadError::Stalled).await;
            }

            let completed = tokio::select! {
                biased;
                _ = self.cancellation.cancelled() => return self.cancelled().await,
                result = in_flight.next() => result.ok_or(DownloadError::Stalled)?,
            };

            match completed.result {
                Ok(bytes) => {
                    pool.record_success(completed.source);
                    received = received.saturating_add(bytes.len() as u64);
                    insert_range(&mut ring, self.spec.page_size, completed.work.range, bytes)?;
                    for (offset, data) in ring.pop_contiguous() {
                        let end = offset.saturating_add(data.len() as u64);
                        self.sink.append(offset, data).await?;
                        committed = end;
                    }
                }
                Err(error) => {
                    pool.record_failure(completed.source, &error);
                    let attempt = completed.work.attempts + 1;
                    if !pool.has_usable() {
                        return self
                            .fail_after_flush(DownloadError::RetryExhausted {
                                range: completed.work.range,
                                attempts: attempt,
                                last_error: error,
                            })
                            .await;
                    }
                    if attempt < self.spec.max_attempts {
                        queue.push_front(WorkItem {
                            range: completed.work.range,
                            attempts: attempt,
                        });
                    } else if let Some((left, right)) =
                        split_range(completed.work.range, self.spec.page_size)
                    {
                        queue.push_front(WorkItem {
                            range: right,
                            attempts: 0,
                        });
                        queue.push_front(WorkItem {
                            range: left,
                            attempts: 0,
                        });
                    } else {
                        return self
                            .fail_after_flush(DownloadError::RetryExhausted {
                                range: completed.work.range,
                                attempts: attempt,
                                last_error: error,
                            })
                            .await;
                    }
                }
            }

            self.publish_progress(
                received,
                committed,
                &ring,
                next_offset,
                furthest_started,
                in_flight.len(),
            );
        }
    }

    fn enqueue_new_work(
        &self,
        expected: u64,
        window_end: u64,
        next_offset: &mut u64,
        queue: &mut VecDeque<WorkItem>,
        in_flight: usize,
    ) -> Result<(), DownloadError> {
        let queue_limit = self.spec.workers.saturating_mul(2).max(1);
        while *next_offset < expected
            && *next_offset < window_end
            && queue.len().saturating_add(in_flight) < queue_limit
        {
            let end = expected
                .min(window_end)
                .min(next_offset.saturating_add(self.spec.block_size as u64));
            queue.push_back(WorkItem {
                range: ByteRange::new(*next_offset, end)?,
                attempts: 0,
            });
            *next_offset = end;
        }
        Ok(())
    }

    fn publish_progress(
        &self,
        received: u64,
        committed: u64,
        ring: &OrderedBuffer,
        next_offset: u64,
        furthest_started: u64,
        in_flight: usize,
    ) {
        self.progress.update(DownloadSnapshot {
            received_bytes: received,
            committed_bytes: committed,
            buffered_pages: ring.ready_pages(),
            window_saturated: next_offset < self.spec.expected_size
                && furthest_started >= ring.window_end_offset(),
            in_flight,
        });
    }

    async fn cancelled<T>(&self) -> Result<T, DownloadError> {
        self.sink.flush().await?;
        Err(DownloadError::Cancelled)
    }

    async fn fail_after_flush<T>(&self, error: DownloadError) -> Result<T, DownloadError> {
        self.sink.flush().await?;
        Err(error)
    }
}

async fn fetch_exact(source: SharedSource, range: ByteRange) -> Result<Bytes, SourceError> {
    let expected = range.length() as usize;
    let mut stream = source.open(range).await?;
    let mut body = BytesMut::with_capacity(expected);
    while let Some(chunk) = stream.next().await {
        let bytes = chunk?;
        if body.len().saturating_add(bytes.len()) > expected {
            return Err(SourceError::new(
                SourceErrorKind::Protocol,
                format!(
                    "range returned more than {expected} bytes (at least {})",
                    body.len() + bytes.len()
                ),
            ));
        }
        body.extend_from_slice(&bytes);
    }
    if body.len() != expected {
        return Err(SourceError::truncated(expected as u64, body.len() as u64));
    }
    Ok(body.freeze())
}

fn insert_range(
    ring: &mut OrderedBuffer,
    page_size: usize,
    range: ByteRange,
    bytes: Bytes,
) -> Result<(), DownloadError> {
    for (index, data) in bytes.chunks(page_size).enumerate() {
        let offset = range
            .start
            .saturating_add(index.saturating_mul(page_size) as u64);
        ring.insert(offset, Bytes::copy_from_slice(data))?;
    }
    Ok(())
}

fn split_range(range: ByteRange, page_size: usize) -> Option<(ByteRange, ByteRange)> {
    if range.length() <= page_size as u64 {
        return None;
    }
    let pages = range.length().div_ceil(page_size as u64);
    let middle = range.start + (pages / 2).max(1) * page_size as u64;
    if middle >= range.end {
        return None;
    }
    Some((
        ByteRange::new(range.start, middle).ok()?,
        ByteRange::new(middle, range.end).ok()?,
    ))
}
