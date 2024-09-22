use crate::python::comment::PyComment;
use crate::reader;

use pyo3::prelude::*;

#[pyfunction(name = "read_comments_from_xml")]
pub fn py_read_comments_from_xml(text: &str, fontsize: f32) -> PyResult<Vec<PyComment>> {
    let comments = reader::xml::read_comments_from_xml(text, fontsize)?;
    Ok(comments.into_iter().map(PyComment::new).collect())
}

#[pyfunction(name = "read_comments_from_protobuf")]
pub fn py_read_comments_from_protobuf(data: &[u8], fontsize: f32) -> PyResult<Vec<PyComment>> {
    let comments = reader::protobuf::read_comments_from_protobuf(data, fontsize)?;
    Ok(comments.into_iter().map(PyComment::new).collect())
}

#[allow(clippy::type_complexity)]
#[pyfunction(name = "parse_special_comment")]
pub fn py_parse_special_comment(
    content: &str,
    zoom_factor: (f32, f32, f32),
) -> PyResult<(
    (i64, i64, f64, f64, f64, f64),
    u8,
    u8,
    String,
    i64,
    f64,
    i64,
    String,
    bool,
)> {
    Ok(reader::special::parse_special_comment(
        content,
        zoom_factor,
    )?)
}
