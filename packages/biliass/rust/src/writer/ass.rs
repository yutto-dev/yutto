use crate::comment::{Comment, CommentPosition};
use crate::writer::utils;

pub fn write_head(
    width: u32,
    height: u32,
    fontface: &str,
    fontsize: f32,
    alpha: f32,
    styleid: &str,
) -> String {
    let alpha = 255 - (alpha * 255.0).round() as u8;
    let outline = f32::max(fontsize / 25.0, 1.0);
    format!("\
[Script Info]
; Script generated by biliass (based on Danmaku2ASS)
; https://github.com/yutto-dev/yutto/tree/main/packages/biliass
Script Updated By: biliass (https://github.com/yutto-dev/yutto/tree/main/packages/biliass)
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
Aspect Ratio: {width}:{height}
Collisions: Normal
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {styleid}, {fontface}, {fontsize:.0}, &H{alpha:02X}FFFFFF, &H{alpha:02X}FFFFFF, &H{alpha:02X}000000, &H{alpha:02X}000000, 0, 0, 0, 0, 100, 100, 0.00, 0.00, 1, {outline:.0}, 0, 7, 0, 0, 0, 0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"
    )
}

fn convert_type2(row: usize, height: u32, bottom_reserved: u32) -> usize {
    height as usize - bottom_reserved as usize - row
}

#[allow(clippy::too_many_arguments)]
pub fn write_comment(
    comment: &Comment,
    row: usize,
    width: u32,
    height: u32,
    bottom_reserved: u32,
    fontsize: f32,
    duration_marquee: f32,
    duration_still: f32,
    styleid: &str,
) -> String {
    let text = utils::ass_escape(&comment.comment);
    let (style, duration) = match comment.pos {
        CommentPosition::Bottom => {
            let halfwidth = width / 2;
            (format!("\\an8\\pos({halfwidth}, {row})"), duration_still)
        }
        CommentPosition::Top => {
            let halfwidth = width / 2;
            let row = convert_type2(row, height, bottom_reserved);
            (format!("\\an2\\pos({halfwidth}, {row})"), duration_still)
        }
        CommentPosition::Reversed => {
            let neglen = -(comment.width.ceil()) as i32;
            (
                format!("\\move({neglen}, {row}, {width}, {row})"),
                duration_marquee,
            )
        }
        _ => {
            let neglen = -(comment.width.ceil()) as i32;
            (
                format!("\\move({width}, {row}, {neglen}, {row})"),
                duration_marquee,
            )
        }
    };
    let mut styles = vec![style];
    if comment.size - fontsize <= -1. || comment.size - fontsize >= 1. {
        styles.push(format!("\\fs{:.0}", comment.size));
    }
    if comment.color != 0xFFFFFF {
        styles.push(format!(
            "\\c&H{}&",
            utils::convert_color(comment.color, None, None)
        ));
        if comment.color == 0x000000 {
            styles.push("\\3c&HFFFFFF&".to_owned());
        }
    }
    let start = utils::convert_timestamp(comment.timeline);
    let end = utils::convert_timestamp(comment.timeline + duration as f64);
    let styles = styles.join("");
    format!("Dialogue: 2,{start},{end},{styleid},,0000,0000,0000,,{{{styles}}}{text}\n")
}