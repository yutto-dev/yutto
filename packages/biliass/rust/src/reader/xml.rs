use crate::comment::{Comment, CommentData, CommentPosition, NormalCommentData};
use crate::error::{BiliassError, DecodeError, ParseError};
use crate::filter::{BlockOptions, should_skip_parse};
use crate::reader::{special, utils};
use quick_xml::events::{BytesStart, Event};
use quick_xml::reader::Reader;
use tracing::warn;

#[derive(PartialEq, Clone)]
enum XmlVersion {
    V1,
    V2,
}

fn parse_raw_p(reader: &mut Reader<&[u8]>, element: &BytesStart) -> Result<String, ParseError> {
    let mut attr_p = None;
    for attr_result in element.attributes() {
        let attr = attr_result.map_err(|e| ParseError::Xml(e.to_string()))?;
        if attr.key.as_ref() == b"p" {
            attr_p = Some(
                attr.decode_and_unescape_value(reader.decoder())
                    .map(|s| s.to_string())
                    .map_err(|e| {
                        ParseError::Xml(format!("Error decoding version attribute: {}", e))
                    })?,
            );
        }
    }
    attr_p.ok_or(ParseError::Xml("No p attribute found".to_string()))
}

fn parse_comment_content(reader: &mut Reader<&[u8]>) -> Result<String, ParseError> {
    let mut content = None;
    let mut buf = Vec::new();

    if let Ok(Event::Text(e)) = reader.read_event_into(&mut buf) {
        content = Some(e.unescape().unwrap().into_owned());
    }
    buf.clear();

    content.ok_or(ParseError::Xml("No content found in comment".to_string()))
}

fn parse_comment_item(
    raw_p: &str,
    content: &str,
    version: XmlVersion,
    fontsize: f32,
    zoom_factor: (f32, f32, f32),
    id: u64,
    block_options: &BlockOptions,
) -> Result<Option<Comment>, ParseError> {
    let split_p = raw_p.split(',').collect::<Vec<&str>>();
    if split_p.len() < 5 {
        return Err(ParseError::Xml(format!(
            "Invalid p attribute: {raw_p}, expected at least 5 parts",
        )));
    }
    let p_offset = if version == XmlVersion::V1 { 0 } else { 2 };
    let danmaku_type_id = split_p[1 + p_offset];
    match danmaku_type_id {
        "1" | "4" | "5" | "6" | "7" => {
            let mut timeline = split_p[p_offset]
                .parse::<f64>()
                .map_err(|e| ParseError::Xml(format!("Error parsing timeline: {}", e)))?;
            if version == XmlVersion::V2 {
                timeline /= 1000.0;
            }
            let timestamp = split_p[4 + p_offset]
                .parse::<u64>()
                .map_err(|e| ParseError::Xml(format!("Error parsing timestamp: {}", e)))?;
            let comment_pos = match danmaku_type_id {
                "1" => CommentPosition::Scroll,
                "4" => CommentPosition::Top,
                "5" => CommentPosition::Bottom,
                "6" => CommentPosition::Reversed,
                "7" => CommentPosition::Special,
                _ => unreachable!("Impossible danmaku type"),
            };
            if should_skip_parse(&comment_pos, block_options) {
                return Ok(None);
            }
            let color = split_p[3 + p_offset]
                .parse::<u32>()
                .map_err(|e| ParseError::Xml(format!("Error parsing color: {}", e)))?;
            let size = split_p[2 + p_offset]
                .parse::<i32>()
                .map_err(|e| ParseError::Xml(format!("Error parsing size: {}", e)))?;
            let (comment_content, size, comment_data) = if comment_pos != CommentPosition::Special {
                let comment_content = utils::unescape_newline(content);
                let size = (size as f32) * fontsize / 25.0;
                let height =
                    (comment_content.chars().filter(|&c| c == '\n').count() as f32 + 1.0) * size;
                let width = utils::calculate_length(&comment_content) * size;
                (
                    comment_content,
                    size,
                    CommentData::Normal(NormalCommentData { height, width }),
                )
            } else {
                let parsed_data =
                    special::parse_special_comment(&utils::filter_bad_chars(content), zoom_factor);
                if parsed_data.is_err() {
                    warn!("Failed to parse special comment: {:?}", parsed_data);
                    return Ok(None);
                }
                let (content, special_comment_data) = parsed_data.unwrap();
                (
                    content,
                    size as f32,
                    CommentData::Special(special_comment_data),
                )
            };
            Ok(Some(Comment {
                timeline,
                timestamp,
                no: id,
                content: comment_content,
                pos: comment_pos,
                color,
                size,
                data: comment_data,
            }))
        }

        // ignore scripted comment
        "8" => Ok(None),

        _ => Err(ParseError::Xml(format!(
            "Unknown danmaku type: {danmaku_type_id}",
        ))),
    }
}

fn parse_comment(
    reader: &mut Reader<&[u8]>,
    element: BytesStart,
    version: XmlVersion,
    fontsize: f32,
    zoom_factor: (f32, f32, f32),
    id: u64,
    block_options: &BlockOptions,
) -> Result<Option<Comment>, ParseError> {
    if version == XmlVersion::V2 {
        return Err(ParseError::Xml("Not implemented".to_string()));
    }
    let raw_p = parse_raw_p(reader, &element)?;
    let content = parse_comment_content(reader)?;
    let parsed_p = parse_comment_item(
        &raw_p,
        &content,
        version.clone(),
        fontsize,
        zoom_factor,
        id,
        block_options,
    )?;
    Ok(parsed_p)
}

pub fn read_comments_from_xml<T>(
    text: T,
    fontsize: f32,
    zoom_factor: (f32, f32, f32),
    block_options: &BlockOptions,
) -> Result<Vec<Comment>, BiliassError>
where
    T: AsRef<str>,
{
    let filtered_text = utils::filter_bad_chars(text.as_ref());
    let mut reader = Reader::from_str(&filtered_text);

    let mut buf = Vec::new();
    let mut comments: Vec<Comment> = Vec::new();
    let mut version: Option<XmlVersion> = None;
    let mut count = 0;

    loop {
        match reader.read_event_into(&mut buf) {
            Err(e) => return Err(BiliassError::from(DecodeError::from(e))),
            // exits the loop when reaching end of file
            Ok(Event::Eof) => {
                break;
            }
            Ok(Event::Decl(decl)) => {
                let version_literal = decl.version().map_err(|e| ParseError::Xml(e.to_string()))?;
                match version_literal.as_ref() {
                    b"1.0" => version = Some(XmlVersion::V1),
                    b"2.0" => version = Some(XmlVersion::V2),
                    _ => {
                        return Err(BiliassError::ParseError(ParseError::Xml(
                            "Unknown XML version".to_string(),
                        )));
                    }
                }
            }
            Ok(Event::Start(e)) => {
                if e.name().as_ref() == b"d" {
                    if version.is_none() {
                        return Err(BiliassError::ParseError(ParseError::Xml(
                            "No version specified".to_string(),
                        )));
                    }
                    if let Ok(comment_option) = parse_comment(
                        &mut reader,
                        e,
                        version.clone().unwrap(),
                        fontsize,
                        zoom_factor,
                        count,
                        block_options,
                    ) {
                        if let Some(comment) = comment_option {
                            comments.push(comment);
                        }
                    } else {
                        eprintln!("Error parsing comment at {:?}", reader.buffer_position());
                    }
                    count += 1;
                }
            }
            _ => (),
        }
        buf.clear();
    }

    Ok(comments)
}
