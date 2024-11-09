use crate::error;
use crate::proto;
use prost::Message;
use pyo3::prelude::*;
use std::io::Cursor;

#[pyfunction(name = "get_danmaku_meta_size")]
pub fn py_get_danmaku_meta_size(buffer: &[u8]) -> PyResult<usize> {
    let dm_sge_opt = proto::danmaku_view::DmWebViewReply::decode(&mut Cursor::new(buffer))
        .map(|reply| reply.dm_sge)
        .map_err(error::DecodeError::from)
        .map_err(error::BiliassError::from)?;

    Ok(dm_sge_opt.map_or(0, |dm_sge| dm_sge.total as usize))
}
