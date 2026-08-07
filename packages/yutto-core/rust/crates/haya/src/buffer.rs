use bytes::Bytes;

use crate::DownloadError;

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

    pub fn pop_contiguous(&mut self) -> Vec<(u64, Bytes)> {
        let mut pages = Vec::new();
        loop {
            let slot = self.head as usize % self.slots.len();
            let Some(data) = self.slots[slot].take() else {
                break;
            };
            let offset = self
                .origin
                .saturating_add(self.head.saturating_mul(self.page_size as u64));
            self.head += 1;
            self.ready -= 1;
            pages.push((offset, data));
        }
        pages
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
        assert!(buffer.pop_contiguous().is_empty());

        buffer
            .insert(100, Bytes::from_static(b"abcd"))
            .expect("first page fits");
        assert_eq!(
            buffer.pop_contiguous(),
            [
                (100, Bytes::from_static(b"abcd")),
                (104, Bytes::from_static(b"efgh")),
            ]
        );
        assert_eq!(buffer.ready_pages(), 0);
        assert_eq!(buffer.window_end_offset(), 120);
    }
}
