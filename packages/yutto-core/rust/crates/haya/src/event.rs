#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DownloadSnapshot {
    pub received_bytes: u64,
    pub committed_bytes: u64,
    pub buffered_pages: usize,
    pub window_saturated: bool,
    pub in_flight: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DownloadReport {
    pub committed_bytes: u64,
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
