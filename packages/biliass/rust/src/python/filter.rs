use crate::{error::BiliassError, filter::BlockOptions};
use pyo3::prelude::*;
use regex::Regex;

#[pyclass(name = "BlockOptions")]
pub struct PyBlockOptions {
    pub block_top: bool,
    pub block_bottom: bool,
    pub block_scroll: bool,
    pub block_reverse: bool,
    pub block_special: bool,
    pub block_colorful: bool,
    pub block_keyword_patterns: Vec<String>,
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
