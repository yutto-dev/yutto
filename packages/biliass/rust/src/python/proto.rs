use crate::error;
use crate::proto;
use prost::Message;
use pyo3::prelude::*;
use std::io::Cursor;

#[pyclass(name = "DanmakuElem")]
pub struct PyDanmakuElem {
    inner: proto::danmaku::DanmakuElem,
}

impl PyDanmakuElem {
    fn new(inner: proto::danmaku::DanmakuElem) -> Self {
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
pub struct PyDmSegMobileReply {
    inner: proto::danmaku::DmSegMobileReply,
}

impl PyDmSegMobileReply {
    fn new(inner: proto::danmaku::DmSegMobileReply) -> Self {
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
            proto::danmaku::DmSegMobileReply::decode(&mut Cursor::new(buffer))
                .map_err(error::DecodeError::from)
                .map_err(error::BiliassError::from)?,
        ))
    }
}

#[pyfunction(name = "get_danmaku_meta_size")]
pub fn py_get_danmaku_meta_size(buffer: &[u8]) -> PyResult<usize> {
    let dm_sge_opt = proto::danmaku_view::DmWebViewReply::decode(&mut Cursor::new(buffer))
        .map(|reply| reply.dm_sge)
        .map_err(error::DecodeError::from)
        .map_err(error::BiliassError::from)?;

    Ok(dm_sge_opt.map_or(0, |dm_sge| dm_sge.total as usize))
}
