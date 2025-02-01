use crate::comment::CommentPosition;
use regex::Regex;

#[derive(Default, Clone)]
pub struct BlockOptions {
    pub block_top: bool,
    pub block_bottom: bool,
    pub block_scroll: bool,
    pub block_reverse: bool,
    pub block_special: bool,
    pub block_colorful: bool,
    pub block_keyword_patterns: Vec<Regex>,
}

pub fn should_skip_parse(pos: &CommentPosition, block_options: &BlockOptions) -> bool {
    matches!(pos, CommentPosition::Top) && block_options.block_top
        || matches!(pos, CommentPosition::Bottom) && block_options.block_bottom
        || matches!(pos, CommentPosition::Scroll) && block_options.block_scroll
        || matches!(pos, CommentPosition::Special) && block_options.block_reverse
}
