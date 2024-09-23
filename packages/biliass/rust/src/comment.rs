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
pub struct Comment {
    /// The position when the comment is replayed
    pub timeline: f64,
    /// The UNIX timestamp when the comment is submitted
    pub timestamp: u64,
    /// A sequence of 1, 2, 3, ..., used for sorting
    pub no: u64,
    /// The content of the comment
    pub comment: String,
    /// The comment position
    pub pos: CommentPosition,
    /// Font color represented in 0xRRGGBB,
    /// e.g. 0xffffff for white
    pub color: u32,
    /// Font size
    pub size: f32,
    /// The estimated height in pixels
    /// i.e. (comment.count('\n')+1)*size
    pub height: f32,
    /// The estimated width in pixels
    /// i.e. calculate_length(comment)*size
    pub width: f32,
}
