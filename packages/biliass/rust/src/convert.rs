use crate::comment::{Comment, CommentPosition};
use crate::error::BiliassError;
use crate::filter::BlockOptions;
use crate::writer;
use crate::writer::rows;
use rayon::prelude::*;

#[allow(clippy::too_many_arguments)]
pub fn process_comments(
    comments: &Vec<Comment>,
    width: u32,
    height: u32,
    zoom_factor: (f32, f32, f32),
    display_region_ratio: f32,
    fontface: &str,
    fontsize: f32,
    alpha: f32,
    duration_marquee: f64,
    duration_still: f64,
    reduced: bool,
) -> Result<String, BiliassError> {
    let styleid = "biliass";
    let mut ass_result = "".to_owned();
    ass_result += &writer::ass::write_head(width, height, fontface, fontsize, alpha, styleid);
    let bottom_reserved = ((height as f32) * (1. - display_region_ratio)) as u32;
    let mut rows = rows::init_rows(4, (height - bottom_reserved + 1) as usize);

    for comment in comments {
        match comment.pos {
            CommentPosition::Scroll
            | CommentPosition::Bottom
            | CommentPosition::Top
            | CommentPosition::Reversed => {
                ass_result += &writer::ass::write_normal_comment(
                    rows.as_mut(),
                    comment,
                    width,
                    height,
                    bottom_reserved,
                    fontsize,
                    duration_marquee,
                    duration_still,
                    styleid,
                    reduced,
                );
            }
            CommentPosition::Special => {
                ass_result += &writer::ass::write_special_comment(
                    comment,
                    width,
                    height,
                    zoom_factor,
                    styleid,
                );
            }
        }
    }
    Ok(ass_result)
}

#[allow(clippy::too_many_arguments)]
pub fn convert_to_ass<Reader, Input>(
    inputs: Vec<Input>,
    reader: Reader,
    stage_width: u32,
    stage_height: u32,
    display_region_ratio: f32,
    font_face: &str,
    font_size: f32,
    text_opacity: f32,
    duration_marquee: f64,
    duration_still: f64,
    is_reduce_comments: bool,
    block_options: &BlockOptions,
) -> Result<String, BiliassError>
where
    Reader: Fn(Input, f32, (f32, f32, f32), &BlockOptions) -> Result<Vec<Comment>, BiliassError>
        + Send
        + Sync,
    Input: Send,
{
    let zoom_factor = crate::writer::utils::get_zoom_factor(
        crate::reader::special::BILI_PLAYER_SIZE,
        (stage_width, stage_height),
    );
    let comments_result: Result<Vec<Vec<Comment>>, BiliassError> = inputs
        .into_par_iter()
        .map(|input| reader(input, font_size, zoom_factor, block_options))
        .collect();

    let comments = comments_result?;
    let mut comments = comments.concat();
    if !block_options.block_keyword_patterns.is_empty() {
        comments.retain(|comment| {
            !block_options
                .block_keyword_patterns
                .iter()
                .any(|regex| regex.is_match(&comment.content))
        });
    }
    if block_options.block_colorful {
        comments.retain(|comment| comment.color == 0xffffff);
    }
    comments.sort_by(|a, b| {
        (
            a.timeline,
            a.timestamp,
            a.no,
            &a.content,
            &a.pos,
            a.color,
            a.size,
        )
            .partial_cmp(&(
                b.timeline,
                b.timestamp,
                b.no,
                &b.content,
                &b.pos,
                b.color,
                a.size,
            ))
            .unwrap_or(std::cmp::Ordering::Less)
    });
    process_comments(
        &comments,
        stage_width,
        stage_height,
        zoom_factor,
        display_region_ratio,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        is_reduce_comments,
    )
}
