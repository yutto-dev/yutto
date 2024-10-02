use crate::{convert, reader};

use pyo3::{
    prelude::*,
    pybacked::{PyBackedBytes, PyBackedStr},
};

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "xml_to_ass")]
pub fn py_xml_to_ass(
    inputs: Vec<PyBackedStr>,
    stage_width: u32,
    stage_height: u32,
    reserve_blank: u32,
    font_face: &str,
    font_size: f32,
    text_opacity: f32,
    duration_marquee: f64,
    duration_still: f64,
    comment_filters: Vec<String>,
    is_reduce_comments: bool,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        crate::reader::xml::read_comments_from_xml,
        stage_width,
        stage_height,
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        comment_filters,
        is_reduce_comments,
    )?)
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "protobuf_to_ass")]
pub fn py_protobuf_to_ass(
    inputs: Vec<PyBackedBytes>,
    stage_width: u32,
    stage_height: u32,
    reserve_blank: u32,
    font_face: &str,
    font_size: f32,
    text_opacity: f32,
    duration_marquee: f64,
    duration_still: f64,
    comment_filters: Vec<String>,
    is_reduce_comments: bool,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        reader::protobuf::read_comments_from_protobuf,
        stage_width,
        stage_height,
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        comment_filters,
        is_reduce_comments,
    )?)
}
