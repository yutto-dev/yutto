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
    file: File,
    committed: u64,
    closed: bool,
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
                file,
                committed,
                closed: false,
            }),
        })
    }
}

#[async_trait]
impl CommitSink for FileSink {
    async fn committed_offset(&self) -> Result<u64, SinkError> {
        Ok(self.state.lock().await.committed)
    }

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        if state.closed {
            return Err(SinkError::new("cannot append to a closed file sink"));
        }
        if offset != state.committed {
            return Err(SinkError::new(format!(
                "append at {offset}, committed offset is {}",
                state.committed
            )));
        }
        let write_result = async {
            state.file.write_all(&data).await?;
            // Tokio may report the buffered write's OS error only when the
            // in-flight blocking operation is polled again.
            state.file.flush().await
        }
        .await;
        if let Err(write_error) = write_result {
            let committed = state.committed;
            let rollback = async {
                state.file.set_len(committed).await?;
                state.file.seek(SeekFrom::Start(committed)).await?;
                Ok::<_, std::io::Error>(())
            }
            .await;
            if let Err(rollback_error) = rollback {
                state.closed = true;
                return Err(SinkError::new(format!(
                    "failed to write output file: {write_error}; failed to restore committed offset {committed}, so the sink was closed: {rollback_error}"
                )));
            }
            return Err(SinkError::new(format!(
                "failed to write output file: {write_error}"
            )));
        }
        state.committed += data.len() as u64;
        Ok(())
    }

    async fn flush(&self) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        state
            .file
            .flush()
            .await
            .map_err(|error| SinkError::new(format!("failed to flush output file: {error}")))
    }

    async fn close(&self) -> Result<(), SinkError> {
        let mut state = self.state.lock().await;
        state
            .file
            .flush()
            .await
            .map_err(|error| SinkError::new(format!("failed to flush output file: {error}")))?;
        state.closed = true;
        Ok(())
    }
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
                file: File::from_std(read_only),
                committed: 0,
                closed: false,
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
}
