use pyo3::prelude::*;

#[pyfunction(name = "enable_tracing")]
pub fn py_enable_tracing() {
    crate::logging::enable_tracing();
}
