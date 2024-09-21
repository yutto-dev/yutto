use crate::writer;

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

// #[pyfunction(name = "test_rows")]
// pub fn py_test_rows(rows: Vec<Vec<PyRef<crate::python::PyOptionComment>>>) -> PyResult<()> {
//     Ok(())
// }
