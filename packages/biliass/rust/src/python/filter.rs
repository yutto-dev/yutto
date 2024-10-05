use crate::{error::BiliassError, filter::BlockOptions};
use pyo3::prelude::*;
use regex::Regex;

#[pyclass(name = "BlockOptions")]
#[derive(Clone)]
pub struct PyBlockOptions {
    pub inner: BlockOptions,
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
        let block_keyword_patterns_res: Result<Vec<Regex>, regex::Error> = block_keyword_patterns
            .into_iter()
            .map(|pattern| regex::Regex::new(&pattern))
            .collect();
        let block_keyword_patterns = block_keyword_patterns_res.map_err(BiliassError::from)?;

        Ok(PyBlockOptions {
            inner: BlockOptions {
                block_top,
                block_bottom,
                block_scroll,
                block_reverse,
                block_special,
                block_colorful,
                block_keyword_patterns,
            },
        })
    }

    #[staticmethod]
    pub fn default() -> Self {
        PyBlockOptions {
            inner: BlockOptions::default(),
        }
    }
}
