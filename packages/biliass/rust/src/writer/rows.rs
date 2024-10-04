use crate::comment::{Comment, CommentPosition};

pub type Rows<'a> = Vec<Vec<Option<&'a Comment>>>;

pub fn init_rows<'a>(num_types: usize, capacity: usize) -> Rows<'a> {
    let mut rows: Rows = Vec::new();
    for _ in 0..num_types {
        let mut type_rows = Vec::with_capacity(capacity);
        for _ in 0..capacity {
            type_rows.push(None);
        }
        rows.push(type_rows);
    }
    rows
}

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
    let comment_data = comment
        .data
        .as_normal()
        .expect("comment_data is not normal");
    if comment.pos == CommentPosition::Bottom || comment.pos == CommentPosition::Top {
        let mut current_row = row;
        while current_row < rowmax && (res as f32) < comment_data.height {
            if target_row != rows[comment_pos_id][current_row] {
                target_row = rows[comment_pos_id][current_row];
                if let Some(target_row) = target_row {
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
            - duration_marquee * (1.0 - width as f64 / (comment_data.width as f64 + width as f64));
        let mut current_row = row;
        while current_row < rowmax && (res as f32) < comment_data.height {
            if target_row != rows[comment_pos_id][current_row] {
                target_row = rows[comment_pos_id][current_row];
                if let Some(target_row) = target_row {
                    let target_row_data = target_row
                        .data
                        .as_normal()
                        .expect("target_row_data is not normal");
                    if target_row.timeline > threshold_time
                        || target_row.timeline
                            + target_row_data.width as f64 * duration_marquee
                                / (target_row_data.width as f64 + width as f64)
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

pub fn find_alternative_row(
    rows: &Rows,
    comment: &Comment,
    height: u32,
    bottom_reserved: u32,
) -> usize {
    let mut res = 0;
    let comment_pos_id = comment.pos.clone() as usize;
    let comment_data = comment
        .data
        .as_normal()
        .expect("comment_data is not normal");
    for row in 0..(height as usize - bottom_reserved as usize - comment_data.height.ceil() as usize)
    {
        match &rows[comment_pos_id][row] {
            None => return row,
            Some(comment) => {
                let comment_res = &rows[comment_pos_id][res].as_ref().expect("res is None");
                if comment.timeline < comment_res.timeline {
                    res = row;
                }
            }
        }
    }
    res
}

pub fn mark_comment_row<'a>(rows: &mut Rows<'a>, comment: &'a Comment, row: usize) {
    let comment_pos_id = comment.pos.clone() as usize;
    let comment_data = comment
        .data
        .as_normal()
        .expect("comment_data is not normal");
    for i in row..(row + comment_data.height.ceil() as usize) {
        if i >= rows[comment_pos_id].len() {
            break;
        }
        rows[comment_pos_id][i] = Some(comment);
    }
}
