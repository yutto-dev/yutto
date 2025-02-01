#[derive(Debug, PartialEq, Clone, PartialOrd)]
pub enum CommentPosition {
    /// Regular moving comment
    Scroll,
    /// Bottom centered comment
    Bottom,
    /// Top centered comment
    Top,
    /// Reversed moving comment
    Reversed,
    /// Special comment
    Special,
}

#[derive(Debug, PartialEq, Clone)]
pub struct NormalCommentData {
    /// The estimated height in pixels
    /// i.e. (comment.count('\n')+1)*size
    pub height: f32,
    /// The estimated width in pixels
    /// i.e. calculate_length(comment)*size
    pub width: f32,
}

#[derive(Debug, PartialEq, Clone)]
pub struct SpecialCommentData {
    pub rotate_y: i64,
    pub rotate_z: i64,
    pub from_x: f64,
    pub from_y: f64,
    pub to_x: f64,
    pub to_y: f64,
    pub from_alpha: u8,
    pub to_alpha: u8,
    pub delay: i64,
    pub lifetime: f64,
    pub duration: i64,
    pub fontface: String,
    pub is_border: bool,
}

#[derive(Debug, PartialEq, Clone)]
pub enum CommentData {
    Normal(NormalCommentData),
    Special(SpecialCommentData),
}

impl CommentData {
    pub fn as_normal(&self) -> Result<&NormalCommentData, &str> {
        match self {
            CommentData::Normal(data) => Ok(data),
            CommentData::Special(_) => Err("CommentData is Special"),
        }
    }

    pub fn as_special(&self) -> Result<&SpecialCommentData, &str> {
        match self {
            CommentData::Normal(_) => Err("CommentData is Normal"),
            CommentData::Special(data) => Ok(data),
        }
    }
}

#[derive(Debug, PartialEq, Clone)]
pub struct Comment {
    /// The position when the comment is replayed
    pub timeline: f64,
    /// The UNIX timestamp when the comment is submitted
    pub timestamp: u64,
    /// A sequence of 1, 2, 3, ..., used for sorting
    pub no: u64,
    /// The content of the comment
    pub content: String,
    /// The comment position
    pub pos: CommentPosition,
    /// Font color represented in 0xRRGGBB,
    /// e.g. 0xffffff for white
    pub color: u32,
    /// Font size
    pub size: f32,
    /// The comment data
    pub data: CommentData,
}
