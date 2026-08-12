use std::{num::NonZeroUsize, sync::Arc};

use async_trait::async_trait;
use bytes::Bytes;

use crate::SinkError;

#[derive(Debug)]
pub struct CommitBatch {
    offset: u64,
    chunks: Box<[Bytes]>,
    len: usize,
}

impl CommitBatch {
    pub fn new(offset: u64, chunks: Vec<Bytes>) -> Result<Self, SinkError> {
        if chunks.is_empty() || chunks.iter().any(Bytes::is_empty) {
            return Err(SinkError::new(
                "a commit batch must contain only non-empty chunks",
            ));
        }
        let len = chunks.iter().try_fold(0_usize, |total, chunk| {
            total
                .checked_add(chunk.len())
                .ok_or_else(|| SinkError::new("commit batch length overflow"))
        })?;
        let len_u64 =
            u64::try_from(len).map_err(|_| SinkError::new("commit batch length exceeds u64"))?;
        offset
            .checked_add(len_u64)
            .ok_or_else(|| SinkError::new("commit batch end offset overflow"))?;
        Ok(Self {
            offset,
            chunks: chunks.into_boxed_slice(),
            len,
        })
    }

    pub fn offset(&self) -> u64 {
        self.offset
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        false
    }

    pub fn end_offset(&self) -> u64 {
        self.offset + u64::try_from(self.len).expect("CommitBatch validated its end offset")
    }

    pub fn chunks(&self) -> &[Bytes] {
        &self.chunks
    }

    pub fn into_chunks(self) -> Box<[Bytes]> {
        self.chunks
    }
}

#[async_trait]
pub trait CommitSink: Send + Sync {
    async fn committed_offset(&self) -> Result<u64, SinkError>;

    async fn append(&self, offset: u64, data: Bytes) -> Result<(), SinkError>;

    /// Preferred upper bound for one append batch. The default preserves the
    /// historical one-page append and cancellation granularity.
    fn append_batch_size_hint(&self) -> Option<NonZeroUsize> {
        None
    }

    /// Appends a contiguous batch. The default implementation may commit a
    /// prefix before returning an error; sinks can override it with stronger
    /// transactional behavior.
    async fn append_batch(&self, batch: CommitBatch) -> Result<(), SinkError> {
        let mut offset = batch.offset();
        for chunk in batch.into_chunks() {
            let chunk_len = u64::try_from(chunk.len())
                .map_err(|_| SinkError::new("commit batch chunk length exceeds u64"))?;
            let next_offset = offset
                .checked_add(chunk_len)
                .ok_or_else(|| SinkError::new("commit batch end offset overflow"))?;
            self.append(offset, chunk).await?;
            offset = next_offset;
        }
        Ok(())
    }

    async fn flush(&self) -> Result<(), SinkError>;

    async fn close(&self) -> Result<(), SinkError> {
        self.flush().await
    }
}

pub(crate) type SharedSink = Arc<dyn CommitSink>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_empty_chunks_and_offset_overflow() {
        assert!(CommitBatch::new(0, Vec::new()).is_err());
        assert!(CommitBatch::new(0, vec![Bytes::new()]).is_err());
        assert!(CommitBatch::new(u64::MAX, vec![Bytes::from_static(b"x")]).is_err());
    }
}
