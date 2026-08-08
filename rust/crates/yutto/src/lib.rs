use std::{
    collections::HashMap,
    path::PathBuf,
    sync::{Arc, Mutex},
    time::Duration,
};

use haya::{
    CommitSink, DownloadSnapshot, DownloadSpec, Downloader, ProgressSink,
    file::{FileOpenMode, FileSink},
};
use haya_http::HttpRangeSource;
use pyo3::{
    create_exception,
    exceptions::{PyException, PyRuntimeError, PyValueError},
    prelude::*,
    types::{PyAny, PyBytes},
};
use reqwest::{Client, Url};
use tokio_util::sync::CancellationToken;

use crate::session::{Response, Session, SessionConfig, SessionError};

pub mod session;

create_exception!(yutto._core, HttpError, PyException);
create_exception!(yutto._core, InvalidUrlError, HttpError);
create_exception!(yutto._core, UnsupportedProtocolError, HttpError);
create_exception!(yutto._core, HttpTimeoutError, HttpError);
create_exception!(yutto._core, HttpTransportError, HttpError);
create_exception!(yutto._core, HttpStatusError, HttpError);
create_exception!(yutto._core, SessionClosedError, HttpError);

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

#[pyclass(frozen, get_all, module = "yutto._core", skip_from_py_object)]
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

#[pyclass(frozen, module = "yutto._core", skip_from_py_object)]
struct NativeResponse {
    response: Response,
}

#[pymethods]
impl NativeResponse {
    #[getter]
    fn status_code(&self) -> u16 {
        self.response.status.as_u16()
    }

    #[getter]
    fn url(&self) -> &str {
        self.response.url.as_str()
    }

    #[getter]
    fn body<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.response.body)
    }

    #[getter]
    fn is_success(&self) -> bool {
        self.response.is_success()
    }

    fn header(&self, name: &str) -> PyResult<Option<&str>> {
        self.response.header(name).map_err(session_error_to_py)
    }

    fn raise_for_status(&self) -> PyResult<()> {
        self.response
            .error_for_status()
            .map_err(session_error_to_py)
    }
}

#[pyclass(frozen, module = "yutto._core")]
struct YuttoSession {
    session: Session,
}

#[pymethods]
impl YuttoSession {
    #[new]
    #[pyo3(signature = (*, headers=None, cookies=None, proxy=None, use_system_proxy=true, accept_invalid_certs=false, ca_cert_file=None, ca_cert_dir=None, read_timeout=5.0, connect_timeout=5.0))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        headers: Option<HashMap<String, String>>,
        cookies: Option<HashMap<String, String>>,
        proxy: Option<String>,
        use_system_proxy: bool,
        accept_invalid_certs: bool,
        ca_cert_file: Option<PathBuf>,
        ca_cert_dir: Option<PathBuf>,
        read_timeout: f64,
        connect_timeout: f64,
    ) -> PyResult<Self> {
        let session = Session::new(SessionConfig {
            headers: headers.unwrap_or_default(),
            cookies: cookies.unwrap_or_default(),
            proxy,
            use_system_proxy,
            accept_invalid_certs,
            ca_cert_file,
            ca_cert_dir,
            read_timeout: duration_from_seconds(read_timeout, "read_timeout")?,
            connect_timeout: duration_from_seconds(connect_timeout, "connect_timeout")?,
        })
        .map_err(session_error_to_py)?;
        Ok(Self { session })
    }

    #[pyo3(signature = (url, *, params=None, headers=None))]
    fn get<'py>(
        &self,
        py: Python<'py>,
        url: String,
        params: Option<Vec<(String, String)>>,
        headers: Option<HashMap<String, String>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let session = self.session.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            session
                .get(url, params.unwrap_or_default(), headers.unwrap_or_default())
                .await
                .map(|response| NativeResponse { response })
                .map_err(session_error_to_py)
        })
    }

    #[pyo3(signature = (name, *, url="https://www.bilibili.com/"))]
    fn cookie(&self, name: &str, url: &str) -> PyResult<Option<String>> {
        self.session.cookie(name, url).map_err(session_error_to_py)
    }

    fn close(&self) {
        self.session.close();
    }

    #[getter]
    fn is_closed(&self) -> bool {
        self.session.is_closed()
    }

    #[pyo3(signature = (sources, target, expected_size, *, overwrite=false, workers=8, block_size=524288))]
    fn start_transfer(
        &self,
        sources: Vec<String>,
        target: PathBuf,
        expected_size: u64,
        overwrite: bool,
        workers: usize,
        block_size: usize,
    ) -> PyResult<TransferHandle> {
        start_transfer_with_session(
            &self.session,
            sources,
            target,
            expected_size,
            overwrite,
            workers,
            block_size,
        )
    }
}

#[pyclass(module = "yutto._core")]
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

fn start_transfer_with_session(
    session: &Session,
    sources: Vec<String>,
    target: PathBuf,
    expected_size: u64,
    overwrite: bool,
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
    let client = session.client().map_err(session_error_to_py)?;

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
    pyo3_async_runtimes::tokio::get_runtime().spawn(async move {
        let result = run_transfer(TransferArgs {
            client,
            sources,
            target,
            overwrite,
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
    client: Client,
    sources: Vec<String>,
    target: PathBuf,
    overwrite: bool,
    spec: DownloadSpec,
    cancellation: CancellationToken,
    state: Arc<Mutex<TransferState>>,
}

async fn run_transfer(args: TransferArgs) -> Result<u64, String> {
    let sources = args
        .sources
        .into_iter()
        .map(|source| {
            let url =
                Url::parse(&source).map_err(|error| format!("invalid source URL: {error}"))?;
            Ok(Arc::new(HttpRangeSource::new(
                args.client.clone(),
                url,
                Default::default(),
                args.spec.expected_size,
            )) as Arc<dyn haya::RangeSource>)
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

fn duration_from_seconds(value: f64, name: &str) -> PyResult<Duration> {
    if !value.is_finite() || value <= 0.0 {
        return Err(PyValueError::new_err(format!(
            "{name} must be a positive finite number"
        )));
    }
    Duration::try_from_secs_f64(value)
        .map_err(|error| PyValueError::new_err(format!("invalid {name}: {error}")))
}

fn session_error_to_py(error: SessionError) -> PyErr {
    let message = error.to_string();
    match error {
        SessionError::InvalidUrl(_) => InvalidUrlError::new_err(message),
        SessionError::UnsupportedProtocol(_) => UnsupportedProtocolError::new_err(message),
        SessionError::Timeout(_) => HttpTimeoutError::new_err(message),
        SessionError::Transport(_) => HttpTransportError::new_err(message),
        SessionError::Status(_) => HttpStatusError::new_err(message),
        SessionError::Closed => SessionClosedError::new_err(message),
        SessionError::Configuration(_) => PyValueError::new_err(message),
    }
}

#[pymodule(gil_used = false)]
#[pyo3(name = "_core")]
fn yutto(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<YuttoSession>()?;
    module.add_class::<NativeResponse>()?;
    module.add_class::<TransferHandle>()?;
    module.add_class::<TransferSnapshot>()?;
    module.add("HttpError", module.py().get_type::<HttpError>())?;
    module.add("InvalidUrlError", module.py().get_type::<InvalidUrlError>())?;
    module.add(
        "UnsupportedProtocolError",
        module.py().get_type::<UnsupportedProtocolError>(),
    )?;
    module.add(
        "HttpTimeoutError",
        module.py().get_type::<HttpTimeoutError>(),
    )?;
    module.add(
        "HttpTransportError",
        module.py().get_type::<HttpTransportError>(),
    )?;
    module.add("HttpStatusError", module.py().get_type::<HttpStatusError>())?;
    module.add(
        "SessionClosedError",
        module.py().get_type::<SessionClosedError>(),
    )?;
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
