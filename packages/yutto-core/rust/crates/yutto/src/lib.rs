use std::{
    collections::HashMap,
    path::PathBuf,
    sync::{Arc, Mutex, OnceLock},
    time::Duration,
};

use haya::{
    CommitSink, DownloadSnapshot, DownloadSpec, Downloader, ProgressSink,
    file::{FileOpenMode, FileSink},
};
use haya_http::HttpRangeSource;
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
};
use reqwest::{
    Client, Proxy, Url,
    header::{HeaderMap, HeaderName, HeaderValue},
};
use tokio::runtime::Runtime;
use tokio_util::sync::CancellationToken;

static RUNTIME: OnceLock<Runtime> = OnceLock::new();

#[derive(Clone, Debug)]
enum TransferOutcome {
    Running,
    Completed(u64),
    Failed(String),
    Cancelled,
}

#[derive(Clone, Debug)]
struct TransferState {
    expected_bytes: u64,
    origin_bytes: u64,
    received_bytes: u64,
    committed_bytes: u64,
    buffered_pages: usize,
    window_saturated: bool,
    in_flight: usize,
    outcome: TransferOutcome,
}

#[pyclass(frozen, get_all, module = "yutto_core._core", skip_from_py_object)]
#[derive(Clone, Debug)]
struct TransferSnapshot {
    expected_bytes: u64,
    origin_bytes: u64,
    received_bytes: u64,
    committed_bytes: u64,
    buffered_pages: usize,
    window_saturated: bool,
    in_flight: usize,
}

#[pyclass(module = "yutto_core._core")]
struct TransferHandle {
    state: Arc<Mutex<TransferState>>,
    cancellation: CancellationToken,
}

#[pymethods]
impl TransferHandle {
    fn done(&self) -> bool {
        !matches!(
            self.state
                .lock()
                .expect("transfer state lock poisoned")
                .outcome,
            TransferOutcome::Running
        )
    }

    fn cancel(&self) {
        self.cancellation.cancel();
    }

    fn snapshot(&self) -> TransferSnapshot {
        let state = self.state.lock().expect("transfer state lock poisoned");
        TransferSnapshot {
            expected_bytes: state.expected_bytes,
            origin_bytes: state.origin_bytes,
            received_bytes: state.received_bytes,
            committed_bytes: state.committed_bytes,
            buffered_pages: state.buffered_pages,
            window_saturated: state.window_saturated,
            in_flight: state.in_flight,
        }
    }

    fn result(&self) -> PyResult<u64> {
        match &self
            .state
            .lock()
            .expect("transfer state lock poisoned")
            .outcome
        {
            TransferOutcome::Running => Err(PyRuntimeError::new_err("transfer is still running")),
            TransferOutcome::Completed(committed) => Ok(*committed),
            TransferOutcome::Failed(error) => Err(PyRuntimeError::new_err(error.clone())),
            TransferOutcome::Cancelled => Err(PyRuntimeError::new_err("transfer was cancelled")),
        }
    }
}

struct StateProgress {
    state: Arc<Mutex<TransferState>>,
}

impl ProgressSink for StateProgress {
    fn update(&self, snapshot: DownloadSnapshot) {
        let mut state = self.state.lock().expect("transfer state lock poisoned");
        state.received_bytes = state.origin_bytes.saturating_add(snapshot.received_bytes);
        state.committed_bytes = snapshot.committed_bytes;
        state.buffered_pages = snapshot.buffered_pages;
        state.window_saturated = snapshot.window_saturated;
        state.in_flight = snapshot.in_flight;
    }
}

#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature = (sources, target, expected_size, *, overwrite=false, headers=None, proxy=None, use_system_proxy=true, accept_invalid_certs=false, workers=8, block_size=524288))]
fn start_transfer(
    sources: Vec<String>,
    target: PathBuf,
    expected_size: u64,
    overwrite: bool,
    headers: Option<HashMap<String, String>>,
    proxy: Option<String>,
    use_system_proxy: bool,
    accept_invalid_certs: bool,
    workers: usize,
    block_size: usize,
) -> PyResult<TransferHandle> {
    if sources.is_empty() {
        return Err(PyValueError::new_err("at least one source is required"));
    }
    if workers == 0 {
        return Err(PyValueError::new_err("workers must be at least 1"));
    }
    if block_size == 0 {
        return Err(PyValueError::new_err("block_size must be at least 1"));
    }
    let spec = transfer_spec(expected_size, workers, block_size);

    let runtime = runtime()?;
    let cancellation = CancellationToken::new();
    let task_cancellation = cancellation.clone();
    let state = Arc::new(Mutex::new(TransferState {
        expected_bytes: expected_size,
        origin_bytes: 0,
        received_bytes: 0,
        committed_bytes: 0,
        buffered_pages: 0,
        window_saturated: false,
        in_flight: 0,
        outcome: TransferOutcome::Running,
    }));
    let task_state = state.clone();
    runtime.spawn(async move {
        let result = run_transfer(TransferArgs {
            sources,
            target,
            overwrite,
            headers: headers.unwrap_or_default(),
            proxy,
            use_system_proxy,
            accept_invalid_certs,
            spec,
            cancellation: task_cancellation.clone(),
            state: task_state.clone(),
        })
        .await;
        let outcome = match result {
            Ok(committed) => TransferOutcome::Completed(committed),
            Err(_error) if task_cancellation.is_cancelled() => TransferOutcome::Cancelled,
            Err(error) => TransferOutcome::Failed(error),
        };
        task_state
            .lock()
            .expect("transfer state lock poisoned")
            .outcome = outcome;
    });

    Ok(TransferHandle {
        state,
        cancellation,
    })
}

struct TransferArgs {
    sources: Vec<String>,
    target: PathBuf,
    overwrite: bool,
    headers: HashMap<String, String>,
    proxy: Option<String>,
    use_system_proxy: bool,
    accept_invalid_certs: bool,
    spec: DownloadSpec,
    cancellation: CancellationToken,
    state: Arc<Mutex<TransferState>>,
}

async fn run_transfer(args: TransferArgs) -> Result<u64, String> {
    let client = build_client(
        args.headers,
        args.proxy,
        args.use_system_proxy,
        args.accept_invalid_certs,
    )?;
    let sources = args
        .sources
        .into_iter()
        .map(|source| {
            let url =
                Url::parse(&source).map_err(|error| format!("invalid source URL: {error}"))?;
            Ok(
                Arc::new(HttpRangeSource::new(client.clone(), url, HeaderMap::new()))
                    as Arc<dyn haya::RangeSource>,
            )
        })
        .collect::<Result<Vec<_>, String>>()?;
    let mode = if args.overwrite {
        FileOpenMode::Overwrite
    } else {
        FileOpenMode::ResumeFromLength
    };
    let sink = Arc::new(
        FileSink::open(args.target, mode)
            .await
            .map_err(|error| error.to_string())?,
    );
    let committed = sink
        .committed_offset()
        .await
        .map_err(|error| error.to_string())?;
    {
        let mut state = args.state.lock().expect("transfer state lock poisoned");
        state.origin_bytes = committed;
        state.received_bytes = committed;
        state.committed_bytes = committed;
    }

    let progress = Arc::new(StateProgress { state: args.state });
    let result = Downloader::new(args.spec, sources, sink.clone())
        .map_err(|error| error.to_string())?
        .with_progress_sink(progress)
        .with_cancellation_token(args.cancellation)
        .run()
        .await;
    let close_result = sink.close().await;
    match (result, close_result) {
        (Ok(report), Ok(())) => Ok(report.committed_bytes),
        (Err(error), _) => Err(error.to_string()),
        (Ok(_), Err(error)) => Err(error.to_string()),
    }
}

fn transfer_spec(expected_size: u64, workers: usize, requested_block_size: usize) -> DownloadSpec {
    let mut spec = DownloadSpec::new(expected_size);
    spec.block_size = requested_block_size;
    spec.workers = workers;
    spec.source_cooldown = Duration::from_millis(500);
    spec
}

fn build_client(
    headers: HashMap<String, String>,
    proxy: Option<String>,
    use_system_proxy: bool,
    accept_invalid_certs: bool,
) -> Result<Client, String> {
    let mut default_headers = HeaderMap::new();
    for (name, value) in headers {
        let name = HeaderName::from_bytes(name.as_bytes())
            .map_err(|error| format!("invalid HTTP header name {name:?}: {error}"))?;
        let value = HeaderValue::from_str(&value)
            .map_err(|error| format!("invalid HTTP header value: {error}"))?;
        default_headers.insert(name, value);
    }

    let mut builder = Client::builder()
        .default_headers(default_headers)
        .danger_accept_invalid_certs(accept_invalid_certs)
        .connect_timeout(Duration::from_secs(3))
        .timeout(Duration::from_secs(7));
    if !use_system_proxy {
        builder = builder.no_proxy();
    }
    if let Some(proxy) = proxy {
        builder = builder.proxy(Proxy::all(&proxy).map_err(|error| error.to_string())?);
    }
    builder.build().map_err(|error| error.to_string())
}

fn runtime() -> PyResult<&'static Runtime> {
    if let Some(runtime) = RUNTIME.get() {
        return Ok(runtime);
    }
    let runtime = Runtime::new()
        .map_err(|error| PyRuntimeError::new_err(format!("failed to start Tokio: {error}")))?;
    let _ = RUNTIME.set(runtime);
    Ok(RUNTIME.get().expect("Tokio runtime was initialized"))
}

#[pymodule(gil_used = false)]
#[pyo3(name = "_core")]
fn yutto(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<TransferHandle>()?;
    module.add_class::<TransferSnapshot>()?;
    module.add_function(wrap_pyfunction!(start_transfer, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use haya::DownloadSpec;

    use super::transfer_spec;

    #[test]
    fn transfer_configuration_keeps_the_fixed_ordered_window() {
        let spec = transfer_spec(1024, 100, 64 * 1024 * 1024);

        assert_eq!(spec.block_size, 64 * 1024 * 1024);
        assert_eq!(spec.window_pages, DownloadSpec::DEFAULT_WINDOW_PAGES);
        assert_eq!(spec.workers, 100);
    }
}
