use crate::comment::CommentPosition;
use crate::error::BiliassError;
use crate::python;
use crate::writer::{self, rows};
use regex::Regex;

use pyo3::prelude::*;

#[pyclass(name = "Rows")]
pub struct PyRows {
    pub inner: rows::Rows,
}

#[pymethods]
impl PyRows {
    #[new]
    fn new(num_types: usize, capacity: usize) -> Self {
        PyRows {
            inner: rows::init_rows(num_types, capacity),
        }
    }
}

#[pyfunction(name = "write_head")]
pub fn py_write_head(
    width: u32,
    height: u32,
    fontface: &str,
    fontsize: f32,
    alpha: f32,
    styleid: &str,
) -> PyResult<String> {
    Ok(writer::ass::write_head(
        width, height, fontface, fontsize, alpha, styleid,
    ))
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "write_normal_comment")]
pub fn py_write_normal_comment(
    rows: &mut python::writer::PyRows,
    comment: &crate::python::PyComment,
    width: u32,
    height: u32,
    bottom_reserved: u32,
    fontsize: f32,
    duration_marquee: f64,
    duration_still: f64,
    styleid: &str,
    reduced: bool,
) -> PyResult<String> {
    Ok(writer::ass::write_normal_comment(
        &mut rows.inner,
        &comment.inner,
        width,
        height,
        bottom_reserved,
        fontsize,
        duration_marquee,
        duration_still,
        styleid,
        reduced,
    ))
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "write_comment_with_animation")]
pub fn py_write_comment_with_animation(
    comment: &crate::python::PyComment,
    width: u32,
    height: u32,
    rotate_y: i64,
    rotate_z: i64,
    from_x: f64,
    from_y: f64,
    to_x: f64,
    to_y: f64,
    from_alpha: u8,
    to_alpha: u8,
    text: &str,
    delay: i64,
    lifetime: f64,
    duration: i64,
    fontface: &str,
    is_border: bool,
    styleid: &str,
    zoom_factor: (f32, f32, f32),
) -> PyResult<String> {
    Ok(writer::ass::write_comment_with_animation(
        &comment.inner,
        width,
        height,
        rotate_y,
        rotate_z,
        from_x,
        from_y,
        to_x,
        to_y,
        from_alpha,
        to_alpha,
        text,
        delay,
        lifetime,
        duration,
        fontface,
        is_border,
        styleid,
        zoom_factor,
    ))
}

#[pyfunction(name = "write_special_comment")]
pub fn py_write_special_comment(
    comment: &crate::python::PyComment,
    width: u32,
    height: u32,
    styleid: &str,
) -> PyResult<String> {
    Ok(writer::ass::write_special_comment(
        &comment.inner,
        width,
        height,
        styleid,
    ))
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "process_comments")]
pub fn py_process_comments(
    comments: Vec<PyRef<crate::python::PyComment>>,
    width: u32,
    height: u32,
    styleid: &str,
    bottom_reserved: u32,
    fontface: &str,
    fontsize: f32,
    alpha: f32,
    duration_marquee: f64,
    duration_still: f64,
    filters_regex: Vec<String>,
    reduced: bool,
) -> PyResult<String> {
    let mut ass_result = "".to_owned();
    ass_result += &writer::ass::write_head(width, height, fontface, fontsize, alpha, styleid);
    let mut rows = rows::init_rows(4, (height - bottom_reserved + 1) as usize);
    let compiled_regexes_res: Result<Vec<Regex>, regex::Error> = filters_regex
        .into_iter()
        .map(|pattern| Regex::new(&pattern))
        .collect();
    let compiled_regexes = compiled_regexes_res.map_err(BiliassError::from)?;
    for comment in comments.into_iter() {
        match comment.inner.pos {
            CommentPosition::Scroll
            | CommentPosition::Bottom
            | CommentPosition::Top
            | CommentPosition::Reversed => {
                if compiled_regexes
                    .iter()
                    .any(|regex| regex.is_match(&comment.inner.comment))
                {
                    continue;
                };
                ass_result += &writer::ass::write_normal_comment(
                    rows.as_mut(),
                    &comment.inner,
                    width,
                    height,
                    bottom_reserved,
                    fontsize,
                    duration_marquee,
                    duration_still,
                    styleid,
                    reduced,
                );
            }
            CommentPosition::Special => {
                ass_result +=
                    &writer::ass::write_special_comment(&comment.inner, width, height, styleid);
            }
        }
    }
    Ok(ass_result)
}
