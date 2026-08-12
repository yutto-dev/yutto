use std::time::Duration;

use tokio::time::Instant;

use crate::{DownloadError, SourceError, source::SharedSource};

#[derive(Debug)]
struct Health {
    failures: usize,
    in_flight: usize,
    disabled: bool,
    ready_at: Instant,
}

pub(crate) struct SourcePool {
    sources: Vec<SharedSource>,
    health: Vec<Health>,
    cooldown: Duration,
}

impl SourcePool {
    pub fn new(sources: Vec<SharedSource>, cooldown: Duration) -> Self {
        let now = Instant::now();
        let health = sources
            .iter()
            .map(|_| Health {
                failures: 0,
                in_flight: 0,
                disabled: false,
                ready_at: now,
            })
            .collect();
        Self {
            sources,
            health,
            cooldown,
        }
    }

    pub fn select(&mut self, now: Instant) -> Option<(usize, SharedSource)> {
        let id = self
            .health
            .iter()
            .enumerate()
            .filter(|(_, health)| !health.disabled && health.ready_at <= now)
            .min_by_key(|(id, health)| (health.failures, health.in_flight, *id))
            .map(|(id, _)| id)?;
        self.health[id].in_flight += 1;
        Some((id, self.sources[id].clone()))
    }

    pub fn record_success(&mut self, id: usize) {
        let health = &mut self.health[id];
        health.in_flight = health.in_flight.saturating_sub(1);
        let now = Instant::now();
        if health.ready_at <= now {
            health.failures = 0;
            health.ready_at = now;
        }
    }

    pub fn record_failure(&mut self, id: usize, error: &SourceError) -> Result<(), DownloadError> {
        let health = &mut self.health[id];
        health.in_flight = health.in_flight.saturating_sub(1);
        health.failures += 1;
        if error.retryable() {
            let multiplier = health.failures.min(8) as u32;
            health.ready_at = Instant::now()
                .checked_add(self.cooldown.saturating_mul(multiplier))
                .ok_or_else(|| DownloadError::InvalidSpec("source_cooldown is too large".into()))?;
        } else {
            health.disabled = true;
        }
        Ok(())
    }

    pub fn has_usable(&self) -> bool {
        self.health.iter().any(|health| !health.disabled)
    }

    pub fn has_ready(&self, now: Instant) -> bool {
        self.health
            .iter()
            .any(|health| !health.disabled && health.ready_at <= now)
    }

    pub fn next_ready_at(&self) -> Option<Instant> {
        self.health
            .iter()
            .filter(|health| !health.disabled)
            .map(|health| health.ready_at)
            .min()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::SourceErrorKind;

    #[test]
    fn sibling_success_does_not_cancel_an_active_cooldown() {
        let mut pool = SourcePool {
            sources: Vec::new(),
            health: vec![Health {
                failures: 0,
                in_flight: 2,
                disabled: false,
                ready_at: Instant::now(),
            }],
            cooldown: Duration::from_secs(1),
        };

        pool.record_failure(
            0,
            &SourceError::new(SourceErrorKind::Timeout, "injected timeout"),
        )
        .expect("cooldown fits in an instant");
        let ready_at = pool.health[0].ready_at;
        pool.record_success(0);

        assert_eq!(pool.health[0].failures, 1);
        assert_eq!(pool.health[0].ready_at, ready_at);
        assert_eq!(pool.health[0].in_flight, 0);
    }
}
