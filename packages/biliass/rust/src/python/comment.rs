use crate::comment;
use pyo3::prelude::*;

#[pyclass(name = "CommentPosition", eq, eq_int)]
#[derive(PartialEq)]
pub enum PyCommentPosition {
    Scroll,
    Bottom,
    Top,
    Reversed,
    Special,
}

#[pyclass(name = "Comment")]
pub struct PyComment {
    inner: comment::Comment,
}

impl PyComment {
    pub fn new(inner: comment::Comment) -> Self {
        PyComment { inner }
    }
}

#[pymethods]
impl PyComment {
    #[getter]
    fn timeline(&self) -> PyResult<f32> {
        Ok(self.inner.timeline)
    }

    #[getter]
    fn timestamp(&self) -> PyResult<u64> {
        Ok(self.inner.timestamp)
    }

    #[getter]
    fn no(&self) -> PyResult<u64> {
        Ok(self.inner.no)
    }

    #[getter]
    fn comment(&self) -> PyResult<String> {
        Ok(self.inner.comment.clone())
    }

    #[getter]
    fn pos(&self) -> PyResult<PyCommentPosition> {
        Ok(match self.inner.pos {
            comment::CommentPosition::Scroll => PyCommentPosition::Scroll,
            comment::CommentPosition::Bottom => PyCommentPosition::Bottom,
            comment::CommentPosition::Top => PyCommentPosition::Top,
            comment::CommentPosition::Reversed => PyCommentPosition::Reversed,
            comment::CommentPosition::Special => PyCommentPosition::Special,
        })
    }

    #[getter]
    fn color(&self) -> PyResult<u32> {
        Ok(self.inner.color)
    }

    #[getter]
    fn size(&self) -> PyResult<f32> {
        Ok(self.inner.size)
    }

    #[getter]
    fn height(&self) -> PyResult<f32> {
        Ok(self.inner.height)
    }

    #[getter]
    fn width(&self) -> PyResult<f32> {
        Ok(self.inner.width)
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("Comment({:?})", self.inner))
    }
}
