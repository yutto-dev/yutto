use std::{pin::Pin, sync::Arc};

use async_trait::async_trait;
use bytes::Bytes;
use futures_util::Stream;

use crate::{ByteRange, SourceError};

pub type ByteStream = Pin<Box<dyn Stream<Item = Result<Bytes, SourceError>> + Send + 'static>>;

#[async_trait]
pub trait RangeSource: Send + Sync {
    async fn open(&self, range: ByteRange) -> Result<ByteStream, SourceError>;
}

pub(crate) type SharedSource = Arc<dyn RangeSource>;
