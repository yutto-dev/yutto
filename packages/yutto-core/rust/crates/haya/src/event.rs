#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DownloadSnapshot {
    /// Unique resource bytes successfully received and accepted during this session.
    ///
    /// Partial bytes from failed attempts and retransmitted physical traffic are excluded.
    pub received_bytes: u64,
    pub committed_bytes: u64,
    pub buffered_pages: usize,
    pub window_saturated: bool,
    pub in_flight: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DownloadReport {
    pub committed_bytes: u64,
    /// Unique resource bytes successfully received and accepted during this session.
    ///
    /// Partial bytes from failed attempts and retransmitted physical traffic are excluded.
    pub received_bytes: u64,
    pub attempts: usize,
}

pub trait ProgressSink: Send + Sync {
    fn update(&self, snapshot: DownloadSnapshot);
}

#[derive(Debug, Default)]
pub struct NullProgressSink;

impl ProgressSink for NullProgressSink {
    fn update(&self, _snapshot: DownloadSnapshot) {}
}
