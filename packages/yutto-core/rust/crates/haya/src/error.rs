use thiserror::Error;

use crate::ByteRange;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SourceErrorKind {
    Timeout,
    Transport,
    Truncated,
    Protocol,
    Other,
}

#[derive(Clone, Debug, Error)]
#[error("{kind:?}: {message}")]
pub struct SourceError {
    pub kind: SourceErrorKind,
    pub message: String,
}

impl SourceError {
    pub fn new(kind: SourceErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }

    pub fn truncated(expected: u64, actual: u64) -> Self {
        Self::new(
            SourceErrorKind::Truncated,
            format!("range ended after {actual} bytes, expected {expected}"),
        )
    }

    pub fn retryable(&self) -> bool {
        matches!(
            self.kind,
            SourceErrorKind::Timeout
                | SourceErrorKind::Transport
                | SourceErrorKind::Truncated
                | SourceErrorKind::Other
        )
    }
}

#[derive(Clone, Debug, Error)]
#[error("{message}")]
pub struct SinkError {
    pub message: String,
}

impl SinkError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

#[derive(Debug, Error)]
pub enum DownloadError {
    #[error("invalid download specification: {0}")]
    InvalidSpec(String),
    #[error("no usable source remains")]
    NoUsableSource,
    #[error("range {range:?} failed after {attempts} attempts: {last_error}")]
    RetryExhausted {
        range: ByteRange,
        attempts: usize,
        last_error: SourceError,
    },
    #[error("ordered buffer rejected a page: {0}")]
    Buffer(String),
    #[error("sink error: {0}")]
    Sink(#[from] SinkError),
    #[error("download was cancelled")]
    Cancelled,
    #[error("scheduler made no progress")]
    Stalled,
}
