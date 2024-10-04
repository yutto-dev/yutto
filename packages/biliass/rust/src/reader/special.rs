use crate::comment::SpecialCommentData;
use crate::error::ParseError;
use crate::reader::utils;

// pub const BILI_PLAYER_SIZE: (u32, u32) = (512, 384); // Bilibili player version 2010
// pub const BILI_PLAYER_SIZE: (u32, u32) = (540, 384); // Bilibili player version 2012
// pub const BILI_PLAYER_SIZE: (u32, u32) = (672, 438); // Bilibili player version 2014
pub const BILI_PLAYER_SIZE: (u32, u32) = (891, 589); // Bilibili player version 2021 (flex)

fn get_position(input_pos: f64, is_height: bool, zoom_factor: (f32, f32, f32)) -> f64 {
    let (zoom, size) = if is_height {
        (zoom_factor.2, BILI_PLAYER_SIZE.1 as f64)
    } else {
        (zoom_factor.1, BILI_PLAYER_SIZE.0 as f64)
    };

    if input_pos < 1. {
        return zoom_factor.0 as f64 * input_pos * size + zoom as f64;
    }
    zoom_factor.0 as f64 * input_pos + zoom as f64
}

#[allow(clippy::type_complexity)]
pub fn parse_special_comment(
    content: &str,
    zoom_factor: (f32, f32, f32),
) -> Result<(String, SpecialCommentData), ParseError> {
    let special_comment_parsed_data =
        serde_json::from_str::<serde_json::Value>(content).map_err(|e| {
            ParseError::SpecialComment(format!(
                "Error occurred while parsing special comment: {e}, content: {content}",
            ))
        })?;
    if !special_comment_parsed_data.is_array() {
        return Err(ParseError::SpecialComment(
            "Special comment is not an array".to_owned(),
        ));
    }
    let special_comment_array = special_comment_parsed_data.as_array().unwrap();
    let text = utils::unescape_newline(special_comment_array[4].as_str().ok_or(
        ParseError::SpecialComment("Text is not a string".to_owned()),
    )?);
    let from_x = parse_array_item_at_index(special_comment_array, 0, 0., parse_float_value)?;
    let from_y = parse_array_item_at_index(special_comment_array, 1, 0., parse_float_value)?;
    let to_x = parse_array_item_at_index(special_comment_array, 7, from_x, parse_float_value)?;
    let to_y = parse_array_item_at_index(special_comment_array, 8, from_y, parse_float_value)?;
    let from_x = get_position(from_x, false, zoom_factor);
    let from_y = get_position(from_y, true, zoom_factor);
    let to_x = get_position(to_x, false, zoom_factor);
    let to_y = get_position(to_y, true, zoom_factor);
    let alpha = parse_array_item_at_index(
        special_comment_array,
        2,
        "1-1".to_owned(),
        parse_string_value,
    )?;
    let alpha_split: Vec<&str> = alpha.split('-').collect();
    let from_alpha = alpha_split
        .first()
        .map(|x| x.parse::<f64>().unwrap_or(1.))
        .unwrap_or(1.);
    let to_alpha = alpha_split
        .get(1)
        .map(|x| x.parse::<f64>().unwrap_or(from_alpha))
        .unwrap_or(1.);
    let from_alpha = 255 - (from_alpha * 255.).round() as u8;
    let to_alpha = 255 - (to_alpha * 255.).round() as u8;
    let rotate_z = parse_array_item_at_index(special_comment_array, 5, 0, parse_int_value)?;
    let rotate_y = parse_array_item_at_index(special_comment_array, 6, 0, parse_int_value)?;
    let lifetime = parse_array_item_at_index(special_comment_array, 3, 4500., parse_float_value)?;
    let duration = parse_array_item_at_index(
        special_comment_array,
        9,
        (lifetime * 1000.) as i64,
        parse_int_value,
    )?;
    let delay = parse_array_item_at_index(special_comment_array, 10, 0, parse_int_value)?;
    let fontface = parse_array_item_at_index(
        special_comment_array,
        12,
        "sans-serif".to_owned(),
        parse_string_value,
    )?;
    // TODO(SigureMo): Check this logic, this just aligns with the original code.
    // let is_border = parse_array_item_at_index(special_comment_array, 11, true, parse_bool_value)?;
    let is_border = true;
    Ok((
        text.to_owned(),
        SpecialCommentData {
            rotate_y,
            rotate_z,
            from_x,
            from_y,
            to_x,
            to_y,
            from_alpha,
            to_alpha,
            delay,
            lifetime,
            duration,
            fontface,
            is_border,
        },
    ))
}

/// A safe way to get item without IndexOutOfBounds error.
fn parse_array_item_at_index<T>(
    array: &[serde_json::Value],
    index: usize,
    default: T,
    item_parser: fn(&serde_json::Value, T) -> Result<T, ParseError>,
) -> Result<T, ParseError> {
    match array.get(index) {
        Some(value) => item_parser(value, default),
        None => Ok(default),
    }
}

fn parse_float_value(value: &serde_json::Value, default: f64) -> Result<f64, ParseError> {
    match value {
        serde_json::Value::Number(num) => Ok(num.as_f64().unwrap_or(default)),
        serde_json::Value::String(str) => Ok(str.parse::<f64>().unwrap_or(default)),
        serde_json::Value::Null => Ok(default),
        _ => Err(ParseError::SpecialComment(
            "Value is not a number".to_owned(),
        )),
    }
}

fn parse_int_value(value: &serde_json::Value, default: i64) -> Result<i64, ParseError> {
    match value {
        serde_json::Value::Number(num) => Ok(num.as_f64().unwrap_or(default as f64) as i64),
        serde_json::Value::String(str) => Ok(str.parse::<f64>().unwrap_or(default as f64) as i64),
        serde_json::Value::Null => Ok(default),
        _ => Err(ParseError::SpecialComment(
            "Value is not a number".to_owned(),
        )),
    }
}

fn parse_string_value(value: &serde_json::Value, _: String) -> Result<String, ParseError> {
    match value {
        serde_json::Value::String(str) => Ok(str.to_owned()),
        _ => Err(ParseError::SpecialComment(
            "Value is not a string".to_owned(),
        )),
    }
}

#[allow(unused)]
fn parse_bool_value(value: &serde_json::Value, default: bool) -> Result<bool, ParseError> {
    match value {
        serde_json::Value::Bool(b) => Ok(*b),
        serde_json::Value::Number(num) => Ok(num.as_i64().unwrap_or(default as i64) != 0),
        _ => Err(ParseError::SpecialComment(
            "Value is not a boolean".to_owned(),
        )),
    }
}
