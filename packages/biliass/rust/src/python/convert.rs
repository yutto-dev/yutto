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
        }
    }
}

fn extract_block_options_from_dict(
    block_options: Bound<'_, PyDict>,
) -> PyResult<crate::filter::BlockOptions> {
    let get_bool_option = |key: &str| -> PyResult<bool> {
        block_options
            .get_item(key)
            .expect("Error getting block_top")
            .unwrap()
            .extract()
    };
    let block_top = get_bool_option("block_top")?;
    let block_bottom = get_bool_option("block_bottom")?;
    let block_scroll = get_bool_option("block_scroll")?;
    let block_reverse = get_bool_option("block_reverse")?;
    let block_special = get_bool_option("block_special")?;
    let block_colorful = get_bool_option("block_colorful")?;
    let block_keyword_patterns = block_options
        .get_item("block_keyword_patterns")
        .expect("Error getting block_keyword_patterns")
        .unwrap()
        .extract::<Vec<String>>()?
        .into_iter()
        .map(|pattern| regex::Regex::new(&pattern))
        .collect::<Result<Vec<regex::Regex>, regex::Error>>()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    Ok(crate::filter::BlockOptions {
        block_top,
        block_bottom,
        block_scroll,
        block_reverse,
        block_special,
        block_colorful,
        block_keyword_patterns,
    })
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "xml_to_ass")]
pub fn py_xml_to_ass(
    inputs: Vec<PyBackedStr>,
    // stage_width: u32,
    // stage_height: u32,
    // reserve_blank: u32,
    // font_face: &str,
    // font_size: f32,
    // text_opacity: f32,
    // duration_marquee: f64,
    // duration_still: f64,
    conversion_options: &PyConversionOptions,
    // block_options: Bound<'_, PyDict>,
    // block_options: &crate::python::filter::PyBlockOptions,
    block_top: bool,
    // block_bottom: bool,
    // block_scroll: bool,
    // block_reverse: bool,
    // block_special: bool,
    // block_colorful: bool,
    // block_keyword_patterns: Vec<String>,
    is_reduce_comments: bool,
) -> PyResult<String> {
    // let block_options = extract_block_options_from_dict(block_options)?;
    // let block_options = crate::filter::BlockOptions {
    //     block_top,
    //     block_bottom,
    //     block_scroll,
    //     block_reverse,
    //     block_special,
    //     block_colorful,
    //     block_keyword_patterns: block_keyword_patterns
    //         .into_iter()
    //         .map(|p| Regex::new(&p).unwrap())
    //         .collect(),
    // };
    let block_options = crate::filter::BlockOptions::default();
    Ok(convert::convert_to_ass(
        inputs,
        crate::reader::xml::read_comments_from_xml,
        // stage_width,
        // stage_height,
        // reserve_blank,
        // font_face,
        // font_size,
        // text_opacity,
        // duration_marquee,
        // duration_still,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.reserve_blank,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        &block_options,
        is_reduce_comments,
    )?)
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "protobuf_to_ass")]
pub fn py_protobuf_to_ass(
    inputs: Vec<PyBackedBytes>,
    // stage_width: u32,
    // stage_height: u32,
    // reserve_blank: u32,
    // font_face: &str,
    // font_size: f32,
    // text_opacity: f32,
    // duration_marquee: f64,
    // duration_still: f64,
    conversion_options: &PyConversionOptions,
    // block_options: &crate::python::filter::PyBlockOptions,
    // block_options: Bound<'_, PyDict>,
    block_top: bool,
    // block_bottom: bool,
    // block_scroll: bool,
    // block_reverse: bool,
    // block_special: bool,
    // block_colorful: bool,
    // block_keyword_patterns: Vec<String>,
    is_reduce_comments: bool,
) -> PyResult<String> {
    // let block_options = extract_block_options_from_dict(block_options)?;
    // let block_options = crate::filter::BlockOptions {
    //     block_top,
    //     block_bottom,
    //     block_scroll,
    //     block_reverse,
    //     block_special,
    //     block_colorful,
    //     block_keyword_patterns: block_keyword_patterns
    //         .into_iter()
    //         .map(|p| Regex::new(&p).unwrap())
    //         .collect(),
    // };
    let block_options = crate::filter::BlockOptions::default();
    Ok(convert::convert_to_ass(
        inputs,
        reader::protobuf::read_comments_from_protobuf,
        // stage_width,
        // stage_height,
        // reserve_blank,
        // font_face,
        // font_size,
        // text_opacity,
        // duration_marquee,
        // duration_still,
        conversion_options.stage_width,
        conversion_options.stage_height,
        conversion_options.reserve_blank,
        &conversion_options.font_face,
        conversion_options.font_size,
        conversion_options.text_opacity,
        conversion_options.duration_marquee,
        conversion_options.duration_still,
        &block_options,
        // &block_options.inner,
        is_reduce_comments,
    )?)
}
