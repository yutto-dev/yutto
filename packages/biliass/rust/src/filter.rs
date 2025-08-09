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

#[inline(always)]
pub fn should_skip_parse(pos: &CommentPosition, block_options: &BlockOptions) -> bool {
    match pos {
        CommentPosition::Top => block_options.block_top,
        CommentPosition::Bottom => block_options.block_bottom,
        CommentPosition::Scroll => block_options.block_scroll,
        CommentPosition::Reversed => block_options.block_reverse,
        CommentPosition::Special => block_options.block_special,
    }
}
