use thiserror::Error;

#[derive(Error, Debug)]
pub enum DecodeError {
    #[error("ProtobufDecodeError: {0}")]
    ProtobufDecodeError(#[from] prost::DecodeError),
    #[error("XMLDecodeError: {0}")]
    XMLDecodeError(#[from] quick_xml::Error),
}

#[derive(Error, Debug)]
pub enum ParseError {
    #[error("XMLParseError: {0}")]
    XMLParseError(String),
    #[error("ProtobufParseError")]
    ProtobufParseError(),
}

#[derive(Error, Debug)]
pub enum BiliassError {
    #[error("ParseError: {0}")]
    ParseError(#[from] ParseError),
    #[error("DecodeError: {0}")]
    DecodeError(#[from] DecodeError),
}
