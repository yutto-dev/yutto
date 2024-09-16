mod proto;

use prost::Message;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::fmt;
use std::io::Cursor;

#[derive(Debug)]
struct ParseError {
    inner: prost::DecodeError,
}

impl std::error::Error for ParseError {}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "ParseError: {}", self.inner)
    }
}

impl std::convert::From<ParseError> for PyErr {
    fn from(err: ParseError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}

#[pyclass(name = "DanmakuElem")]
struct PyDanmakuElem {
    inner: proto::DanmakuElem,
}

impl PyDanmakuElem {
    fn new(inner: proto::DanmakuElem) -> Self {
        PyDanmakuElem { inner }
    }
}

#[pymethods]
impl PyDanmakuElem {
    #[getter]
    fn id(&self) -> PyResult<i64> {
        Ok(self.inner.id)
    }

    #[getter]
    fn progress(&self) -> PyResult<i32> {
        Ok(self.inner.progress)
    }

    #[getter]
    fn mode(&self) -> PyResult<i32> {
        Ok(self.inner.mode)
    }

    #[getter]
    fn fontsize(&self) -> PyResult<i32> {
        Ok(self.inner.fontsize)
    }

    #[getter]
    fn color(&self) -> PyResult<u32> {
        Ok(self.inner.color)
    }

    #[getter]
    fn mid_hash(&self) -> PyResult<String> {
        Ok(self.inner.mid_hash.clone())
    }

    #[getter]
    fn content(&self) -> PyResult<String> {
        Ok(self.inner.content.clone())
    }

    #[getter]
    fn ctime(&self) -> PyResult<i64> {
        Ok(self.inner.ctime)
    }

    #[getter]
    fn weight(&self) -> PyResult<i32> {
        Ok(self.inner.weight)
    }

    #[getter]
    fn action(&self) -> PyResult<String> {
        Ok(self.inner.action.clone())
    }

    #[getter]
    fn pool(&self) -> PyResult<i32> {
        Ok(self.inner.pool)
    }

    #[getter]
    fn id_str(&self) -> PyResult<String> {
        Ok(self.inner.id_str.clone())
    }

    #[getter]
    fn attr(&self) -> PyResult<i32> {
        Ok(self.inner.attr)
    }

    #[getter]
    fn animation(&self) -> PyResult<String> {
        Ok(self.inner.animation.clone())
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("DanmakuElem({:?})", self.inner))
    }
}

#[pyclass(name = "DmSegMobileReply")]
struct PyDmSegMobileReply {
    inner: proto::DmSegMobileReply,
}

impl PyDmSegMobileReply {
    fn new(inner: proto::DmSegMobileReply) -> Self {
        PyDmSegMobileReply { inner }
    }
}

#[pymethods]
impl PyDmSegMobileReply {
    #[getter]
    fn elems(&self) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let list = pyo3::types::PyList::empty_bound(py);
            for item in &self.inner.elems {
                let item = PyDanmakuElem::new(item.clone());
                list.append(item.into_py(py))?;
            }
            Ok(list.into())
        })
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("DmSegMobileReply({:?})", self.inner))
    }

    #[staticmethod]
    fn decode(buffer: &[u8]) -> PyResult<Self> {
        Ok(PyDmSegMobileReply::new(
            proto::DmSegMobileReply::decode(&mut Cursor::new(buffer))
                .map_err(|e| ParseError { inner: e })?,
        ))
    }
}

/// Bindings for biliass core.
#[pymodule]
#[pyo3(name = "_core")]
fn bind_biliass_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyDmSegMobileReply>()?;
    Ok(())
}
