use crate::error::BiliassError;
use crate::filter::BlockOptions;
use crate::python::PyBlockOptions;
use crate::{convert, reader};
use pyo3::{
    conversion,
    prelude::*,
    pybacked::{PyBackedBytes, PyBackedStr},
    types::PyDict,
};
use regex::Regex;

#[pyclass(name = "ConversionOptions")]
pub struct PyConversionOptions {
    pub stage_width: u32,
    pub stage_height: u32,
    pub reserve_blank: u32,
    pub font_face: String,
    pub font_size: f32,
    pub text_opacity: f32,
    pub duration_marquee: f64,
    pub duration_still: f64,
    pub is_reduce_comments: bool,
    pub block_options: PyBlockOptions,
}

#[pymethods]
impl PyConversionOptions {
    #[new]
    fn new(
        stage_width: u32,
        stage_height: u32,
        reserve_blank: u32,
        font_face: String,
        font_size: f32,
        text_opacity: f32,
        duration_marquee: f64,
        duration_still: f64,
        is_reduce_comments: bool,
        block_options: &PyBlockOptions,
    ) -> Self {
        PyConversionOptions {
            stage_width,
            stage_height,
            reserve_blank,
            font_face,
            font_size,
            text_opacity,
            duration_marquee,
            duration_still,
            is_reduce_comments,
            block_options: block_options.clone(),
            // block_options: PyBlockOptions::default(),
        }
    }
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "xml_to_ass")]
pub fn py_xml_to_ass(
    inputs: Vec<PyBackedStr>,
    conversion_options: &PyConversionOptions,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        crate::reader::xml::read_comments_from_xml,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.reserve_blank,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        &conversion_options.block_options.to_block_options()?,
        conversion_options.is_reduce_comments,
    )?)
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "protobuf_to_ass")]
pub fn py_protobuf_to_ass(
    inputs: Vec<PyBackedBytes>,
    conversion_options: &PyConversionOptions,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        reader::protobuf::read_comments_from_protobuf,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.reserve_blank,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        &conversion_options.block_options.to_block_options()?,
        conversion_options.is_reduce_comments,
    )?)
}
