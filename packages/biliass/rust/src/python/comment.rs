use crate::comment;
use pyo3::prelude::*;

#[pyclass(name = "CommentPosition", eq, eq_int, hash, frozen)]
#[derive(PartialEq, Hash)]
pub enum PyCommentPosition {
    Scroll,
    Bottom,
    Top,
    Reversed,
    Special,
}

#[pymethods]
impl PyCommentPosition {
    #[getter]
    fn id(&self) -> PyResult<u8> {
        Ok(match self {
            PyCommentPosition::Scroll => 0,
            PyCommentPosition::Bottom => 1,
            PyCommentPosition::Top => 2,
            PyCommentPosition::Reversed => 3,
            PyCommentPosition::Special => 4,
        })
    }
}

#[pyclass(name = "Comment", frozen)]
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
    fn timeline(&self) -> f64 {
        self.inner.timeline
    }

    #[getter]
    fn timestamp(&self) -> u64 {
        self.inner.timestamp
    }

    #[getter]
    fn no(&self) -> u64 {
        self.inner.no
    }

    #[getter]
    fn comment(&self) -> &str {
        &self.inner.comment
    }

    #[getter]
    fn pos(&self) -> PyCommentPosition {
        match self.inner.pos {
            comment::CommentPosition::Scroll => PyCommentPosition::Scroll,
            comment::CommentPosition::Bottom => PyCommentPosition::Bottom,
            comment::CommentPosition::Top => PyCommentPosition::Top,
            comment::CommentPosition::Reversed => PyCommentPosition::Reversed,
            comment::CommentPosition::Special => PyCommentPosition::Special,
        }
    }

    #[getter]
    fn color(&self) -> u32 {
        self.inner.color
    }

    #[getter]
    fn size(&self) -> f32 {
        self.inner.size
    }

    #[getter]
    fn height(&self) -> f32 {
        self.inner.height
    }

    #[getter]
    fn width(&self) -> f32 {
        self.inner.width
    }

    fn __repr__(&self) -> String {
        format!("Comment({:?})", self.inner)
    }
}

#[pyclass(name = "OptionComment", frozen)]
pub struct PyOptionComment {
    inner: Option<comment::Comment>,
}

impl PyOptionComment {
    pub fn new(inner: Option<comment::Comment>) -> Self {
        PyOptionComment { inner }
    }
}

#[pymethods]
impl PyOptionComment {
    fn is_none(&self) -> bool {
        self.inner.is_none()
    }

    fn is_some(&self) -> bool {
        self.inner.is_some()
    }

    fn unwrap(&self) -> PyComment {
        PyComment::new(self.inner.clone().unwrap())
    }

    #[staticmethod]
    fn from_comment(comment: &PyComment) -> Self {
        PyOptionComment {
            inner: Some(comment.inner.clone()),
        }
    }

    #[staticmethod]
    fn none() -> Self {
        PyOptionComment { inner: None }
    }

    fn __eq__(&self, other: &PyOptionComment) -> bool {
        self.inner == other.inner
    }
}
