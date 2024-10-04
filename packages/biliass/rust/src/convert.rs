use crate::comment::{Comment, CommentPosition};
use crate::error::BiliassError;
use crate::writer;
use crate::writer::rows;
use rayon::prelude::*;
use regex::Regex;

#[allow(clippy::too_many_arguments)]
pub fn process_comments(
    comments: &Vec<Comment>,
    width: u32,
    height: u32,
    zoom_factor: (f32, f32, f32),
    bottom_reserved: u32,
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
    reserve_blank: u32,
    font_face: &str,
    font_size: f32,
    text_opacity: f32,
    duration_marquee: f64,
    duration_still: f64,
    filters_regex: Vec<String>,
    is_reduce_comments: bool,
) -> Result<String, BiliassError>
where
    Reader: Fn(Input, f32, (f32, f32, f32)) -> Result<Vec<Comment>, BiliassError> + Send + Sync,
    Input: Send,
{
    let zoom_factor = crate::writer::utils::get_zoom_factor(
        crate::reader::special::BILI_PLAYER_SIZE,
        (stage_width, stage_height),
    );
    let comments_result: Result<Vec<Vec<Comment>>, BiliassError> = inputs
        .into_par_iter()
        .map(|input| reader(input, font_size, zoom_factor))
        .collect();

    let compiled_regexes_res: Result<Vec<Regex>, regex::Error> = filters_regex
        .into_iter()
        .map(|pattern| Regex::new(&pattern))
        .collect();

    let compiled_regexes = compiled_regexes_res.map_err(BiliassError::from)?;
    let comments = comments_result?;
    let comments = comments.concat();
    let mut comments: Vec<Comment> = comments
        .into_iter()
        .filter(|comment| {
            !compiled_regexes
                .iter()
                .any(|regex| regex.is_match(&comment.content))
        })
        .collect();
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
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        is_reduce_comments,
    )
}
