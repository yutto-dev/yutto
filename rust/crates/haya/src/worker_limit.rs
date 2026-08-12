use std::sync::Arc;

use tokio::sync::{OwnedSemaphorePermit, Semaphore};

use crate::DownloadError;

#[derive(Clone, Debug)]
pub struct WorkerLimit {
    capacity: usize,
    semaphore: Arc<Semaphore>,
}

impl WorkerLimit {
    pub fn new(capacity: usize) -> Result<Self, DownloadError> {
        if capacity == 0 || capacity > Semaphore::MAX_PERMITS {
            return Err(DownloadError::InvalidSpec(format!(
                "worker limit capacity must be between 1 and {}",
                Semaphore::MAX_PERMITS
            )));
        }
        Ok(Self {
            capacity,
            semaphore: Arc::new(Semaphore::new(capacity)),
        })
    }

    pub fn capacity(&self) -> usize {
        self.capacity
    }

    pub(crate) fn try_acquire_owned(&self) -> Option<OwnedSemaphorePermit> {
        self.semaphore.clone().try_acquire_owned().ok()
    }

    pub(crate) async fn acquire_owned(self) -> OwnedSemaphorePermit {
        self.semaphore
            .acquire_owned()
            .await
            .expect("Haya never closes a worker limit")
    }
}
