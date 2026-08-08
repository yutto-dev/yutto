use std::sync::Arc;

use async_trait::async_trait;
use bytes::Bytes;

use crate::SinkError;

#[async_trait]
pub trait CommitSink: Send + Sync {
    async fn committed_offset(&self) -> Result<u64, SinkError>;

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError>;

    async fn flush(&self) -> Result<(), SinkError>;

    async fn close(&self) -> Result<(), SinkError> {
        self.flush().await
    }
}

pub(crate) type SharedSink = Arc<dyn CommitSink>;
