mod comment;
mod convert;
mod error;
mod filter;
mod logging;
mod proto;
mod python;
mod reader;
mod writer;

use error::BiliassError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

impl std::convert::From<BiliassError> for PyErr {
    fn from(err: BiliassError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}

/// Bindings for biliass core.
#[pymodule(gil_used = false)]
#[pyo3(name = "_core")]
fn biliass_pyo3(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(python::py_get_danmaku_meta_size, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_xml_to_ass, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_protobuf_to_ass, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_enable_tracing, m)?)?;
    m.add_class::<python::PyBlockOptions>()?;
    m.add_class::<python::PyConversionOptions>()?;
    Ok(())
}
