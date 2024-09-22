use crate::python;
use crate::writer::{self, rows};

use pyo3::prelude::*;

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
    rotate_y: f64,
    rotate_z: f64,
    from_x: f64,
    from_y: f64,
    to_x: f64,
    to_y: f64,
    from_alpha: u8,
    to_alpha: u8,
    text: &str,
    delay: f64,
    lifetime: f64,
    duration: f64,
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
