use crate::comment::{Comment, CommentPosition};

pub type Rows = Vec<Vec<Option<Comment>>>;

#[allow(clippy::too_many_arguments)]
pub fn test_free_rows(
    rows: &Rows,
    comment: &Comment,
    row: usize,
    width: u32,
    height: u32,
    bottom_reserved: u32,
    duration_marquee: f64,
    duration_still: f64,
) -> usize {
    let mut res = 0;
    let rowmax = (height - bottom_reserved) as usize;
    let mut target_row = None;
    let comment_pos_id = comment.pos.clone() as usize;
    if comment.pos == CommentPosition::Bottom || comment.pos == CommentPosition::Top {
        let mut current_row = row;
        while current_row < rowmax && (res as f32) < comment.height {
            if target_row != rows[comment_pos_id][current_row] {
                target_row = rows[comment_pos_id][current_row].clone();
                if let Some(target_row) = target_row.clone() {
                    if target_row.timeline + duration_still > comment.timeline {
                        break;
                    }
                }
            }
            current_row += 1;
            res += 1;
        }
    } else {
        let threshold_time: f64 = comment.timeline
            - duration_marquee * (1.0 - width as f64 / (comment.width as f64 + width as f64));
        let mut current_row = row;
        while current_row < rowmax && (res as f32) < comment.height {
            if target_row != rows[comment_pos_id][current_row] {
                target_row = rows[comment_pos_id][current_row].clone();
                if let Some(target_row) = target_row.clone() {
                    if target_row.timeline > threshold_time
                        || target_row.timeline
                            + target_row.width as f64 * duration_marquee
                                / (target_row.width as f64 + width as f64)
                            > comment.timeline
                    {
                        break;
                    }
                }
            }
            current_row += 1;
            res += 1;
        }
    }
    res
}
