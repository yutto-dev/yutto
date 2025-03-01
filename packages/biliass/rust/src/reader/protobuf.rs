use crate::comment::{Comment, CommentData, CommentPosition, NormalCommentData};
use crate::error::{BiliassError, DecodeError};
use crate::filter::{BlockOptions, should_skip_parse};
use crate::proto::danmaku::DmSegMobileReply;
use crate::reader::{special, utils};
use prost::Message;
use std::io::Cursor;
use tracing::warn;

pub fn read_comments_from_protobuf<T>(
    data: T,
    fontsize: f32,
    zoom_factor: (f32, f32, f32),
    block_options: &BlockOptions,
) -> Result<Vec<Comment>, BiliassError>
where
    T: AsRef<[u8]>,
{
    let replies = DmSegMobileReply::decode(&mut Cursor::new(data))
        .map_err(DecodeError::from)
        .map_err(BiliassError::from)?;
    let mut comments = Vec::new();
    for (i, elem) in replies.elems.into_iter().enumerate() {
        match elem.mode {
            1 | 4 | 5 | 6 | 7 => {
                let timeline = elem.progress as f64 / 1000.0;
                let timestamp = elem.ctime as u64;
                let comment_pos = match elem.mode {
                    1 => CommentPosition::Scroll,
                    4 => CommentPosition::Top,
                    5 => CommentPosition::Bottom,
                    6 => CommentPosition::Reversed,
                    7 => CommentPosition::Special,
                    _ => unreachable!("Impossible danmaku type"),
                };
                if should_skip_parse(&comment_pos, block_options) {
                    continue;
                }
                let color = elem.color;
                let size = elem.fontsize;
                let (comment_content, size, comment_data) =
                    if comment_pos != CommentPosition::Special {
                        let comment_content =
                            utils::unescape_newline(&utils::filter_bad_chars(&elem.content));
                        let size = (size as f32) * fontsize / 25.0;
                        let height =
                            (comment_content.chars().filter(|&c| c == '\n').count() as f32 + 1.0)
                                * size;
                        let width = utils::calculate_length(&comment_content) * size;
                        (
                            comment_content,
                            size,
                            CommentData::Normal(NormalCommentData { height, width }),
                        )
                    } else {
                        let parsed_data = special::parse_special_comment(
                            &utils::filter_bad_chars(&elem.content),
                            zoom_factor,
                        );
                        if parsed_data.is_err() {
                            warn!("Failed to parse special comment: {:?}", parsed_data);
                            continue;
                        }
                        let (content, special_comment_data) = parsed_data.unwrap();
                        (
                            content,
                            size as f32,
                            CommentData::Special(special_comment_data),
                        )
                    };
                comments.push(Comment {
                    timeline,
                    timestamp,
                    no: i as u64,
                    content: comment_content,
                    pos: comment_pos,
                    color,
                    size,
                    data: comment_data,
                })
            }
            8 => {
                // ignore scripted comment
            }
            _ => {
                eprintln!("Unknown danmaku type: {}", elem.mode);
            }
        }
    }
    Ok(comments)
}
