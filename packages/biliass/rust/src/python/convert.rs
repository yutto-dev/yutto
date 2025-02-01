use crate::error::BiliassError;
use crate::filter::BlockOptions;
use crate::{convert, reader};
use pyo3::{
    prelude::*,
    pybacked::{PyBackedBytes, PyBackedStr},
};
use regex::Regex;

#[pyclass(name = "BlockOptions")]
#[derive(Clone)]
pub struct PyBlockOptions {
    pub block_top: bool,
    pub block_bottom: bool,
    pub block_scroll: bool,
    pub block_reverse: bool,
    pub block_special: bool,
    pub block_colorful: bool,
    pub block_keyword_patterns: Vec<String>,
}

impl PyBlockOptions {
    pub fn to_block_options(&self) -> Result<BlockOptions, BiliassError> {
        let block_keyword_patterns_res: Result<Vec<Regex>, regex::Error> = self
            .block_keyword_patterns
            .iter()
            .map(|pattern| regex::Regex::new(pattern))
            .collect();
        let block_keyword_patterns = block_keyword_patterns_res.map_err(BiliassError::from)?;
        Ok(BlockOptions {
            block_top: self.block_top,
            block_bottom: self.block_bottom,
            block_scroll: self.block_scroll,
            block_reverse: self.block_reverse,
            block_special: self.block_special,
            block_colorful: self.block_colorful,
            block_keyword_patterns,
        })
    }
}

#[pymethods]
impl PyBlockOptions {
    #[new]
    fn new(
        block_top: bool,
        block_bottom: bool,
        block_scroll: bool,
        block_reverse: bool,
        block_special: bool,
        block_colorful: bool,
        block_keyword_patterns: Vec<String>,
    ) -> PyResult<Self> {
        Ok(PyBlockOptions {
            block_top,
            block_bottom,
            block_scroll,
            block_reverse,
            block_special,
            block_colorful,
            block_keyword_patterns,
        })
    }

    #[staticmethod]
    pub fn default() -> Self {
        PyBlockOptions {
            block_top: false,
            block_bottom: false,
            block_scroll: false,
            block_reverse: false,
            block_special: false,
            block_colorful: false,
            block_keyword_patterns: vec![],
        }
    }
}

#[pyclass(name = "ConversionOptions")]
pub struct PyConversionOptions {
    pub stage_width: u32,
    pub stage_height: u32,
    pub display_region_ratio: f32,
    pub font_face: String,
    pub font_size: f32,
    pub text_opacity: f32,
    pub duration_marquee: f64,
    pub duration_still: f64,
    pub is_reduce_comments: bool,
}

#[pymethods]
#[allow(clippy::too_many_arguments)]
impl PyConversionOptions {
    #[new]
    fn new(
        stage_width: u32,
        stage_height: u32,
        display_region_ratio: f32,
        font_face: String,
        font_size: f32,
        text_opacity: f32,
        duration_marquee: f64,
        duration_still: f64,
        is_reduce_comments: bool,
    ) -> Self {
        PyConversionOptions {
            stage_width,
            stage_height,
            display_region_ratio,
            font_face,
            font_size,
            text_opacity,
            duration_marquee,
            duration_still,
            is_reduce_comments,
        }
    }
}

#[pyfunction(name = "xml_to_ass")]
pub fn py_xml_to_ass(
    inputs: Vec<PyBackedStr>,
    conversion_options: &PyConversionOptions,
    block_options: &PyBlockOptions,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        crate::reader::xml::read_comments_from_xml,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.display_region_ratio,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        conversion_options.is_reduce_comments,
        &block_options.to_block_options()?,
    )?)
}

#[pyfunction(name = "protobuf_to_ass")]
pub fn py_protobuf_to_ass(
    inputs: Vec<PyBackedBytes>,
    conversion_options: &PyConversionOptions,
    block_options: &PyBlockOptions,
) -> PyResult<String> {
    Ok(convert::convert_to_ass(
        inputs,
        reader::protobuf::read_comments_from_protobuf,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.display_region_ratio,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        conversion_options.is_reduce_comments,
        &block_options.to_block_options()?,
    )?)
}
