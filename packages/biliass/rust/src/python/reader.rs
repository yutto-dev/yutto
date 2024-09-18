use crate::python::comment::PyComment;
use crate::reader;

use pyo3::prelude::*;

#[pyfunction(name = "read_comments_from_xml")]
pub fn py_read_comments_from_xml(text: &str, fontsize: f32) -> PyResult<Vec<PyComment>> {
    let comments = reader::xml::read_comments_from_xml(text, fontsize)?;
    Ok(comments.into_iter().map(PyComment::new).collect())
}
