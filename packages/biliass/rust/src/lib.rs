mod comment;
mod convert;
mod error;
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
#[pymodule]
#[pyo3(name = "_core")]
fn biliass_pyo3(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<python::PyDmSegMobileReply>()?;
    m.add_class::<python::PyDanmakuElem>()?;
    m.add_class::<python::PyComment>()?;
    m.add_class::<python::PyCommentPosition>()?;
    m.add_function(wrap_pyfunction!(python::py_read_comments_from_xml, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_read_comments_from_protobuf, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_parse_special_comment, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_xml_to_ass, m)?)?;
    m.add_function(wrap_pyfunction!(python::py_protobuf_to_ass, m)?)?;
    Ok(())
}
