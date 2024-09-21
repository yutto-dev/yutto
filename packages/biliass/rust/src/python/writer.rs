use crate::python;
use crate::writer::{self, rows};

use pyo3::prelude::*;

use super::PyOptionComment;

#[pyfunction(name = "convert_timestamp")]
pub fn py_convert_timestamp(timestamp: f64) -> PyResult<String> {
    Ok(writer::utils::convert_timestamp(timestamp))
}

#[pyfunction(name = "ass_escape")]
pub fn py_ass_escape(text: &str) -> PyResult<String> {
    Ok(writer::utils::ass_escape(text))
}

#[pyfunction(name = "convert_color")]
#[pyo3(signature = (rgb, width = 1280, height = 576))]
pub fn py_convert_color(rgb: u32, width: u32, height: u32) -> PyResult<String> {
    Ok(writer::utils::convert_color(rgb, Some(width), Some(height)))
}

#[pyfunction(name = "get_zoom_factor")]
pub fn py_get_zoom_factor(
    source_size: (u32, u32),
    target_size: (u32, u32),
) -> PyResult<(f32, f32, f32)> {
    Ok(writer::utils::get_zoom_factor(source_size, target_size))
}

#[pyfunction(name = "convert_flash_rotation")]
pub fn py_convert_flash_rotation(
    rot_y: f64,
    rot_z: f64,
    x: f64,
    y: f64,
    width: f64,
    height: f64,
) -> PyResult<(f64, f64, f64, f64, f64, f64, f64)> {
    Ok(writer::utils::convert_flash_rotation(
        rot_y, rot_z, x, y, width, height,
    ))
}

#[pyclass(name = "Rows")]
pub struct PyRows {
    pub inner: rows::Rows,
}

#[pymethods]
impl PyRows {
    #[new]
    fn new(num_types: usize, capacity: usize) -> Self {
        let mut rows: rows::Rows = Vec::new();
        for _ in 0..num_types {
            let mut type_rows = Vec::with_capacity(capacity);
            for _ in 0..capacity {
                type_rows.push(None);
            }
            rows.push(type_rows);
        }
        PyRows { inner: rows }
    }

    fn get(&self, row: usize, col: usize) -> PyOptionComment {
        PyOptionComment::new(self.inner[row][col].clone())
    }

    fn set(&mut self, row: usize, col: usize, value: PyRef<PyOptionComment>) {
        self.inner[row][col] = value.inner.clone();
    }
}

#[allow(clippy::too_many_arguments)]
#[pyfunction(name = "test_free_rows")]
pub fn py_test_free_rows(
    rows: &python::writer::PyRows,
    comment: &crate::python::PyComment,
    row: usize,
    width: u32,
    height: u32,
    bottom_reserved: u32,
    duration_marquee: f64,
    duration_still: f64,
) -> PyResult<usize> {
    Ok(writer::rows::test_free_rows(
        &rows.inner,
        &comment.inner,
        row,
        width,
        height,
        bottom_reserved,
        duration_marquee,
        duration_still,
    ))
}

#[pyfunction(name = "find_alternative_row")]
pub fn py_find_alternative_row(
    rows: &python::writer::PyRows,
    comment: &crate::python::PyComment,
    height: u32,
    bottom_reserved: u32,
) -> PyResult<usize> {
    Ok(writer::rows::find_alternative_row(
        &rows.inner,
        &comment.inner,
        height,
        bottom_reserved,
    ))
}

#[pyfunction(name = "mark_comment_row")]
pub fn py_mark_comment_row(
    rows: &mut python::writer::PyRows,
    comment: &crate::python::PyComment,
    row: usize,
) -> PyResult<()> {
    writer::rows::mark_comment_row(&mut rows.inner, &comment.inner, row);
    Ok(())
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
#[pyfunction(name = "write_comment")]
pub fn py_write_comment(
    comment: &crate::python::PyComment,
    row: usize,
    width: u32,
    height: u32,
    bottom_reserved: u32,
    fontsize: f32,
    duration_marquee: f64,
    duration_still: f64,
    styleid: &str,
) -> PyResult<String> {
    Ok(writer::ass::write_comment(
        &comment.inner,
        row,
        width,
        height,
        bottom_reserved,
        fontsize,
        duration_marquee,
        duration_still,
        styleid,
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
// pub fn write_normal_comment(
//     rows: &mut rows::Rows,
//     comment: &Comment,
//     width: u32,
//     height: u32,
//     bottom_reserved: u32,
//     fontsize: f32,
//     duration_marquee: f64,
//     duration_still: f64,
//     styleid: &str,
//     reduced: bool,
// ) -> String {
