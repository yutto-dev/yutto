use std::{io::IoSlice, num::NonZeroUsize, path::Path};

use async_trait::async_trait;
use bytes::{Buf, Bytes};
use tokio::{
    fs::{File, OpenOptions},
    io::{AsyncSeekExt, AsyncWriteExt, SeekFrom},
    sync::Mutex,
};

use crate::{CommitBatch, CommitSink, SinkError};

const FILE_APPEND_BATCH_SIZE: usize = 1024 * 1024;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FileOpenMode {
    Overwrite,
    /// Continue from the existing file length.
    ///
    /// The caller must ensure that the existing bytes are a prefix of the same
    /// resource identity. Length alone cannot detect a different resource with
    /// the same size.
    ResumeFromLength,
}

pub struct FileSink {
    state: Mutex<FileState>,
}

struct FileState {
    file: Option<File>,
    committed: u64,
    closed: bool,
    poisoned: bool,
    #[cfg(test)]
    fail_write_after_chunks: Option<usize>,
    #[cfg(test)]
    fail_flush: bool,
}

struct ChunkCursor<'a> {
    chunks: &'a [Bytes],
    chunk_index: usize,
    chunk_offset: usize,
    remaining: usize,
}

impl<'a> ChunkCursor<'a> {
    fn new(chunks: &'a [Bytes]) -> Self {
        let remaining = chunks.iter().fold(0_usize, |total, chunk| {
            total
                .checked_add(chunk.len())
                .expect("CommitBatch validated its total length")
        });
        Self {
            chunks,
            chunk_index: 0,
            chunk_offset: 0,
            remaining,
        }
    }
}

impl Buf for ChunkCursor<'_> {
    fn remaining(&self) -> usize {
        self.remaining
    }

    fn chunk(&self) -> &[u8] {
        self.chunks
            .get(self.chunk_index)
            .map_or(&[], |chunk| &chunk[self.chunk_offset..])
    }

    fn advance(&mut self, mut count: usize) {
        assert!(count <= self.remaining, "cannot advance beyond the batch");
        self.remaining -= count;
        while count > 0 {
            let available = self.chunks[self.chunk_index].len() - self.chunk_offset;
            if count < available {
                self.chunk_offset += count;
                return;
            }
            count -= available;
            self.chunk_index += 1;
            self.chunk_offset = 0;
        }
    }

    fn chunks_vectored<'a>(&'a self, destination: &mut [IoSlice<'a>]) -> usize {
        if destination.is_empty() {
            return 0;
        }
        let Some((first, rest)) = self
            .chunks
            .get(self.chunk_index..)
            .and_then(|chunks| chunks.split_first())
        else {
            return 0;
        };
        let mut written = 0;
        if let Some(slot) = destination.get_mut(written) {
            *slot = IoSlice::new(&first[self.chunk_offset..]);
            written += 1;
        }
        for chunk in rest {
            let Some(slot) = destination.get_mut(written) else {
                break;
            };
            *slot = IoSlice::new(chunk);
            written += 1;
        }
        written
    }
}

impl FileSink {
    pub async fn open(path: impl AsRef<Path>, mode: FileOpenMode) -> Result<Self, SinkError> {
        let mut options = OpenOptions::new();
        options.create(true).write(true);
        match mode {
            FileOpenMode::Overwrite => {
                options.truncate(true);
            }
            FileOpenMode::ResumeFromLength => {}
        }

        let mut file = options.open(path.as_ref()).await.map_err(|error| {
            SinkError::new(format!(
                "failed to open {}: {error}",
                path.as_ref().display()
            ))
        })?;
        let committed = match mode {
            FileOpenMode::Overwrite => 0,
            FileOpenMode::ResumeFromLength => file
                .seek(SeekFrom::End(0))
                .await
                .map_err(|error| SinkError::new(format!("failed to seek output file: {error}")))?,
        };

        Ok(Self {
            state: Mutex::new(FileState {
                file: Some(file),
                committed,
                closed: false,
                poisoned: false,
                #[cfg(test)]
                fail_write_after_chunks: None,
                #[cfg(test)]
                fail_flush: false,
            }),
        })
    }
}

#[async_trait]
impl CommitSink for FileSink {
    async fn committed_offset(&self) -> Result<u64, SinkError> {
        let state = self.state.lock().await;
        if state.poisoned {
            return Err(cancelled_append_error());
        }
        Ok(state.committed)
    }

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError> {
        if data.is_empty() {
            let state = self.state.lock().await;
            if state.closed {
                return Err(SinkError::new("cannot append to a closed file sink"));
            }
            if state.poisoned {
                return Err(cancelled_append_error());
            }
            if offset != state.committed {
                return Err(SinkError::new(format!(
                    "append at {offset}, committed offset is {}",
                    state.committed
                )));
            }
            return Ok(());
        }
        let batch = CommitBatch::new(offset, vec![data])?;
        self.append_batch(batch).await
    }

    fn append_batch_size_hint(&self) -> Option<NonZeroUsize> {
        NonZeroUsize::new(FILE_APPEND_BATCH_SIZE)
    }

    async fn append_batch(&self, batch: CommitBatch) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        if state.closed {
            return Err(SinkError::new("cannot append to a closed file sink"));
        }
        if state.poisoned {
            return Err(cancelled_append_error());
        }
        if batch.offset() != state.committed {
            return Err(SinkError::new(format!(
                "append at {}, committed offset is {}",
                batch.offset(),
                state.committed
            )));
        }
        let committed = state.committed;
        let end_offset = batch.end_offset();
        #[cfg(test)]
        let fail_write_after_chunks = state.fail_write_after_chunks;
        #[cfg(test)]
        let fail_flush = state.fail_flush;
        state.poisoned = true;
        let file = state.file.as_mut().expect("an open sink retains its file");
        let write_result = async {
            #[cfg(test)]
            if let Some(chunk_count) = fail_write_after_chunks {
                let mut cursor =
                    ChunkCursor::new(&batch.chunks()[..chunk_count.min(batch.chunks().len())]);
                file.write_all_buf(&mut cursor).await?;
                return Err(std::io::Error::other("injected batch write failure"));
            }
            let mut cursor = ChunkCursor::new(batch.chunks());
            file.write_all_buf(&mut cursor).await?;
            // Tokio may report the buffered write's OS error only when the
            // in-flight blocking operation is polled again.
            #[cfg(test)]
            if fail_flush {
                return Err(std::io::Error::other("injected batch flush failure"));
            }
            file.flush().await
        }
        .await;
        if let Err(write_error) = write_result {
            let file = state
                .file
                .as_mut()
                .expect("an open sink retains its file until close");
            let rollback = async {
                file.set_len(committed).await?;
                file.seek(SeekFrom::Start(committed)).await?;
                Ok::<_, std::io::Error>(())
            }
            .await;
            if let Err(rollback_error) = rollback {
                state.closed = true;
                state.file.take();
                return Err(SinkError::new(format!(
                    "failed to write output file: {write_error}; failed to restore committed offset {committed}, so the sink was closed: {rollback_error}"
                )));
            }
            state.poisoned = false;
            return Err(SinkError::new(format!(
                "failed to write output file: {write_error}"
            )));
        }
        state.committed = end_offset;
        state.poisoned = false;
        Ok(())
    }

    async fn flush(&self) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        if state.poisoned {
            return Err(cancelled_append_error());
        }
        let Some(file) = state.file.as_mut() else {
            return Ok(());
        };
        file.flush()
            .await
            .map_err(|error| SinkError::new(format!("failed to flush output file: {error}")))
    }

    async fn close(&self) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        if state.poisoned {
            state.closed = true;
            state.file.take();
            return Err(cancelled_append_error());
        }
        let Some(file) = state.file.as_mut() else {
            state.closed = true;
            return Ok(());
        };
        file.flush()
            .await
            .map_err(|error| SinkError::new(format!("failed to flush output file: {error}")))?;
        state.closed = true;
        state.file.take();
        Ok(())
    }
}

fn cancelled_append_error() -> SinkError {
    SinkError::new("file sink is unusable because an append was cancelled")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn poisons_the_sink_when_a_failed_write_cannot_be_rolled_back() {
        let temporary = tempfile::NamedTempFile::new().expect("temporary file");
        let read_only = std::fs::OpenOptions::new()
            .read(true)
            .open(temporary.path())
            .expect("open read-only file");
        let sink = FileSink {
            state: Mutex::new(FileState {
                file: Some(File::from_std(read_only)),
                committed: 0,
                closed: false,
                poisoned: false,
                fail_write_after_chunks: None,
                fail_flush: false,
            }),
        };

        let first = sink
            .append(0, Bytes::from_static(b"data"))
            .await
            .expect_err("read-only file rejects writes");
        assert!(first.message.contains("sink was closed"));
        let second = sink
            .append(0, Bytes::from_static(b"data"))
            .await
            .expect_err("poisoned sink rejects reuse");
        assert_eq!(second.message, "cannot append to a closed file sink");
    }

    #[tokio::test]
    async fn close_releases_the_file_handle() {
        let temporary = tempfile::NamedTempFile::new().expect("temporary file");
        let sink = FileSink::open(temporary.path(), FileOpenMode::Overwrite)
            .await
            .expect("open file sink");

        sink.close().await.expect("close file sink");

        let state = sink.state.lock().await;
        assert!(state.closed);
        assert!(state.file.is_none());
    }

    #[tokio::test]
    async fn rejects_reuse_after_an_append_future_is_dropped() {
        use std::{future::Future, task::Context};

        use futures_util::task::noop_waker_ref;

        let temporary = tempfile::NamedTempFile::new().expect("temporary file");
        let sink = FileSink::open(temporary.path(), FileOpenMode::Overwrite)
            .await
            .expect("open file sink");
        let mut append = Box::pin(sink.append(0, Bytes::from(vec![0; 16 * 1024 * 1024])));
        let mut context = Context::from_waker(noop_waker_ref());

        assert!(append.as_mut().poll(&mut context).is_pending());
        drop(append);

        assert!(sink.committed_offset().await.is_err());
        assert!(sink.append(0, Bytes::from_static(b"tail")).await.is_err());
        assert!(sink.close().await.is_err());
        assert!(sink.state.lock().await.file.is_none());
    }

    #[tokio::test]
    async fn rolls_back_a_partially_written_batch_and_allows_retry() {
        let temporary = tempfile::NamedTempFile::new().expect("temporary file");
        let sink = FileSink::open(temporary.path(), FileOpenMode::Overwrite)
            .await
            .expect("open file sink");
        sink.state.lock().await.fail_write_after_chunks = Some(1);

        let failed = sink
            .append_batch(
                CommitBatch::new(
                    0,
                    vec![Bytes::from_static(b"first"), Bytes::from_static(b"second")],
                )
                .expect("valid batch"),
            )
            .await;

        assert!(failed.is_err());
        assert_eq!(sink.committed_offset().await.expect("offset"), 0);
        assert!(
            std::fs::read(temporary.path())
                .expect("read file")
                .is_empty()
        );

        sink.state.lock().await.fail_write_after_chunks = None;
        sink.append(0, Bytes::from_static(b"retry"))
            .await
            .expect("retry succeeds");
        assert_eq!(
            std::fs::read(temporary.path()).expect("read file"),
            b"retry"
        );
    }

    #[tokio::test]
    async fn rolls_back_a_batch_when_its_flush_fails() {
        let temporary = tempfile::NamedTempFile::new().expect("temporary file");
        let sink = FileSink::open(temporary.path(), FileOpenMode::Overwrite)
            .await
            .expect("open file sink");
        sink.state.lock().await.fail_flush = true;

        let failed = sink.append(0, Bytes::from_static(b"uncommitted")).await;

        assert!(failed.is_err());
        assert_eq!(sink.committed_offset().await.expect("offset"), 0);
        assert!(
            std::fs::read(temporary.path())
                .expect("read file")
                .is_empty()
        );
    }
}
