use std::time::Duration;

use tokio::time::Instant;

use crate::{SourceError, source::SharedSource};

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
        health.failures = 0;
        health.ready_at = Instant::now();
    }

    pub fn record_failure(&mut self, id: usize, error: &SourceError) {
        let health = &mut self.health[id];
        health.in_flight = health.in_flight.saturating_sub(1);
        health.failures += 1;
        if error.retryable() {
            let multiplier = u32::try_from(health.failures.min(8)).unwrap_or(8);
            health.ready_at = Instant::now() + self.cooldown.saturating_mul(multiplier);
        } else {
            health.disabled = true;
        }
    }

    pub fn has_usable(&self) -> bool {
        self.health.iter().any(|health| !health.disabled)
    }

    pub fn next_ready_at(&self) -> Option<Instant> {
        self.health
            .iter()
            .filter(|health| !health.disabled)
            .map(|health| health.ready_at)
            .min()
    }
}
