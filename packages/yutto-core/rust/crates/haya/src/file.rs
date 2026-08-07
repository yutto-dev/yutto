use std::path::Path;

use async_trait::async_trait;
use bytes::Bytes;
use tokio::{
    fs::{File, OpenOptions},
    io::{AsyncSeekExt, AsyncWriteExt, SeekFrom},
    sync::Mutex,
};

use crate::{CommitSink, SinkError};

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
        let mut state = self.state.lock().await;
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
        state.poisoned = true;
        let file = state.file.as_mut().expect("an open sink retains its file");
        let write_result = async {
            file.write_all(&data).await?;
            // Tokio may report the buffered write's OS error only when the
            // in-flight blocking operation is polled again.
            file.flush().await
        }
        .await;
        if let Err(write_error) = write_result {
            let committed = state.committed;
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
        state.committed += data.len() as u64;
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
}
