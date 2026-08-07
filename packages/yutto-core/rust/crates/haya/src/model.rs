use std::time::Duration;

use crate::DownloadError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ByteRange {
    pub start: u64,
    pub end: u64,
}

impl ByteRange {
    pub fn new(start: u64, end: u64) -> Result<Self, DownloadError> {
        if start >= end {
            return Err(DownloadError::InvalidSpec(
                "a byte range must have start < end".into(),
            ));
        }
        Ok(Self { start, end })
    }

    pub const fn length(self) -> u64 {
        self.end - self.start
    }
}

#[derive(Clone, Debug)]
pub struct DownloadSpec {
    pub expected_size: u64,
    pub page_size: usize,
    pub block_size: usize,
    pub window_pages: usize,
    pub workers: usize,
    pub max_attempts: usize,
    pub source_cooldown: Duration,
    pub attempt_timeout: Duration,
}

impl DownloadSpec {
    pub const DEFAULT_PAGE_SIZE: usize = 64 * 1024;
    pub const DEFAULT_BLOCK_SIZE: usize = 512 * 1024;
    pub const DEFAULT_WINDOW_PAGES: usize = 128;
    pub const DEFAULT_WORKERS: usize = 8;
    pub const DEFAULT_MAX_ATTEMPTS: usize = 3;

    pub fn new(expected_size: u64) -> Self {
        Self {
            expected_size,
            page_size: Self::DEFAULT_PAGE_SIZE,
            block_size: Self::DEFAULT_BLOCK_SIZE,
            window_pages: Self::DEFAULT_WINDOW_PAGES,
            workers: Self::DEFAULT_WORKERS,
            max_attempts: Self::DEFAULT_MAX_ATTEMPTS,
            source_cooldown: Duration::from_millis(250),
            attempt_timeout: Duration::from_secs(30),
        }
    }

    pub(crate) fn validate(mut self) -> Result<Self, DownloadError> {
        if self.page_size == 0 {
            return Err(DownloadError::InvalidSpec(
                "page_size must be positive".into(),
            ));
        }
        if self.block_size == 0 {
            return Err(DownloadError::InvalidSpec(
                "block_size must be positive".into(),
            ));
        }
        if self.window_pages == 0 {
            return Err(DownloadError::InvalidSpec(
                "window_pages must be positive".into(),
            ));
        }
        if self.workers == 0 {
            return Err(DownloadError::InvalidSpec(
                "workers must be positive".into(),
            ));
        }
        if self.max_attempts == 0 {
            return Err(DownloadError::InvalidSpec(
                "max_attempts must be positive".into(),
            ));
        }
        if self.attempt_timeout.is_zero() {
            return Err(DownloadError::InvalidSpec(
                "attempt_timeout must be positive".into(),
            ));
        }

        let pages_per_block = self
            .block_size
            .div_ceil(self.page_size)
            .min(self.window_pages);
        self.block_size = pages_per_block
            .checked_mul(self.page_size)
            .ok_or_else(|| DownloadError::InvalidSpec("block_size overflow".into()))?;
        Ok(self)
    }
}
