use crate::comment::{Comment, CommentPosition};
use crate::error::{BiliassError, DecodeError};
use crate::proto::danmaku::DmSegMobileReply;
use crate::reader::utils;
use prost::Message;
use std::io::Cursor;

pub fn read_comments_from_protobuf<T>(data: T, fontsize: f32) -> Result<Vec<Comment>, BiliassError>
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
                let color = elem.color;
                let size = elem.fontsize;
                let (comment_content, size, height, width) =
                    if comment_pos != CommentPosition::Special {
                        let comment_content =
                            utils::unescape_newline(&utils::filter_bad_chars(&elem.content));
                        let size = (size as f32) * fontsize / 25.0;
                        let height =
                            (comment_content.chars().filter(|&c| c == '\n').count() as f32 + 1.0)
                                * size;
                        let width = utils::calculate_length(&comment_content) * size;
                        (comment_content, size, height, width)
                    } else {
                        (utils::filter_bad_chars(&elem.content), size as f32, 0., 0.)
                    };
                comments.push(Comment {
                    timeline,
                    timestamp,
                    no: i as u64,
                    comment: comment_content,
                    pos: comment_pos,
                    color,
                    size,
                    height,
                    width,
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
