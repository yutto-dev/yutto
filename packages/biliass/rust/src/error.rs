use thiserror::Error;

#[derive(Error, Debug)]
pub enum DecodeError {
    #[error("Protobuf: {0}")]
    Protobuf(#[from] prost::DecodeError),
    #[error("Xml: {0}")]
    Xml(#[from] quick_xml::Error),
    #[error("SpecialComment: {0}")]
    SpecialComment(#[from] serde_json::Error),
}

#[derive(Error, Debug)]
pub enum ParseError {
    #[error("Xml: {0}")]
    Xml(String),
    #[error("Protobuf")]
    Protobuf(),
    #[error("SpecialComment: {0}")]
    SpecialComment(String),
}

#[allow(clippy::enum_variant_names)]
#[derive(Error, Debug)]
pub enum BiliassError {
    #[error("ParseError: {0}")]
    ParseError(#[from] ParseError),
    #[error("DecodeError: {0}")]
    DecodeError(#[from] DecodeError),
    #[error("InvalidRegexError: {0}")]
    InvalidRegexError(#[from] regex::Error),
}
