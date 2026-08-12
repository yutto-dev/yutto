use bytes::Bytes;

use crate::{CommitBatch, DownloadError};

#[derive(Debug)]
pub(crate) struct OrderedBuffer {
    origin: u64,
    page_size: usize,
    head: u64,
    slots: Vec<Option<Bytes>>,
    ready: usize,
}

impl OrderedBuffer {
    pub fn new(origin: u64, page_size: usize, capacity: usize) -> Result<Self, DownloadError> {
        if page_size == 0 || capacity == 0 {
            return Err(DownloadError::Buffer(
                "page size and capacity must be positive".into(),
            ));
        }
        Ok(Self {
            origin,
            page_size,
            head: 0,
            slots: vec![None; capacity],
            ready: 0,
        })
    }

    pub fn ready_pages(&self) -> usize {
        self.ready
    }

    pub fn window_end_offset(&self) -> u64 {
        self.origin.saturating_add(
            (self.head + self.slots.len() as u64).saturating_mul(self.page_size as u64),
        )
    }

    pub fn insert(&mut self, offset: u64, data: Bytes) -> Result<(), DownloadError> {
        let relative = offset.checked_sub(self.origin).ok_or_else(|| {
            DownloadError::Buffer(format!("page at {offset} precedes buffer origin"))
        })?;
        if relative % self.page_size as u64 != 0 {
            return Err(DownloadError::Buffer(format!(
                "page at {offset} is not aligned to the buffer origin"
            )));
        }
        let page = relative / self.page_size as u64;
        if page < self.head {
            return Ok(());
        }
        if page >= self.head + self.slots.len() as u64 {
            return Err(DownloadError::Buffer(format!(
                "page {page} is outside [{}, {})",
                self.head,
                self.head + self.slots.len() as u64
            )));
        }

        let slot = page as usize % self.slots.len();
        if let Some(existing) = &self.slots[slot] {
            if existing == &data {
                return Ok(());
            }
            return Err(DownloadError::Buffer(format!(
                "ring slot for page {page} is already occupied"
            )));
        }
        self.slots[slot] = Some(data);
        self.ready += 1;
        Ok(())
    }

    pub fn pop_contiguous_batch(
        &mut self,
        max_bytes: usize,
    ) -> Result<Option<CommitBatch>, DownloadError> {
        if max_bytes == 0 {
            return Err(DownloadError::Buffer(
                "commit batch size must be positive".into(),
            ));
        }
        let first_offset = self
            .origin
            .checked_add(
                self.head
                    .checked_mul(self.page_size as u64)
                    .ok_or_else(|| DownloadError::Buffer("page offset overflow".into()))?,
            )
            .ok_or_else(|| DownloadError::Buffer("page offset overflow".into()))?;
        let mut chunks = Vec::new();
        let mut len = 0_usize;
        loop {
            let slot = self.head as usize % self.slots.len();
            let Some(data) = self.slots[slot].as_ref() else {
                break;
            };
            if !chunks.is_empty() && len.saturating_add(data.len()) > max_bytes {
                break;
            }
            let data = self.slots[slot]
                .take()
                .expect("the contiguous slot was checked above");
            len = len
                .checked_add(data.len())
                .ok_or_else(|| DownloadError::Buffer("commit batch length overflow".into()))?;
            self.head += 1;
            self.ready -= 1;
            chunks.push(data);
        }
        if chunks.is_empty() {
            return Ok(None);
        }
        CommitBatch::new(first_offset, chunks)
            .map(Some)
            .map_err(Into::into)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn releases_only_the_contiguous_prefix() {
        let mut buffer = OrderedBuffer::new(100, 4, 3).expect("valid buffer");
        buffer
            .insert(104, Bytes::from_static(b"efgh"))
            .expect("second page fits");
        assert!(
            buffer
                .pop_contiguous_batch(usize::MAX)
                .expect("valid batch")
                .is_none()
        );

        buffer
            .insert(100, Bytes::from_static(b"abcd"))
            .expect("first page fits");
        let batch = buffer
            .pop_contiguous_batch(usize::MAX)
            .expect("valid batch")
            .expect("contiguous batch");
        assert_eq!(batch.offset(), 100);
        assert_eq!(
            batch.chunks(),
            [Bytes::from_static(b"abcd"), Bytes::from_static(b"efgh")]
        );
        assert_eq!(buffer.ready_pages(), 0);
        assert_eq!(buffer.window_end_offset(), 120);
    }

    #[test]
    fn releases_contiguous_pages_in_bounded_batches() {
        let mut buffer = OrderedBuffer::new(100, 4, 5).expect("valid buffer");
        for (offset, bytes) in [
            (100, &b"aaaa"[..]),
            (104, &b"bbbb"[..]),
            (108, &b"cccc"[..]),
            (112, &b"dddd"[..]),
            (116, &b"e"[..]),
        ] {
            buffer
                .insert(offset, Bytes::copy_from_slice(bytes))
                .expect("page fits");
        }

        let first = buffer
            .pop_contiguous_batch(8)
            .expect("valid batch")
            .expect("first batch");
        let second = buffer
            .pop_contiguous_batch(8)
            .expect("valid batch")
            .expect("second batch");
        let third = buffer
            .pop_contiguous_batch(8)
            .expect("valid batch")
            .expect("third batch");

        assert_eq!((first.offset(), first.len()), (100, 8));
        assert_eq!((second.offset(), second.len()), (108, 8));
        assert_eq!((third.offset(), third.len()), (116, 1));
        assert!(
            buffer
                .pop_contiguous_batch(8)
                .expect("valid batch")
                .is_none()
        );
    }
}
