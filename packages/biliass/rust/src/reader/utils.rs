use std::borrow::Cow;

#[inline]
fn is_bad_char(c: char) -> bool {
    ('\u{00}'..='\u{08}').contains(&c)
        || c == '\u{0b}'
        || c == '\u{0c}'
        || c == '\u{2028}'
        || c == '\u{2029}'
        || ('\u{0e}'..='\u{1f}').contains(&c)
}

/// Filter out bad control characters. Returns Cow::Borrowed when no
/// replacements are needed (the common case), avoiding allocation.
pub fn filter_bad_chars(string: &str) -> Cow<'_, str> {
    if !string.chars().any(is_bad_char) {
        return Cow::Borrowed(string);
    }

    Cow::Owned(
        string
            .chars()
            .map(|c| if is_bad_char(c) { '\u{fffd}' } else { c })
            .collect(),
    )
}

/// Calculate the display length of the longest line in a string.
pub fn calculate_length(s: &str) -> f32 {
    s.split('\n')
        .map(|line| line.chars().count())
        .max()
        .unwrap_or(0) as f32
}

/// Unescape "/n" to actual newline. Returns Cow::Borrowed when no
/// replacements are needed, avoiding allocation.
#[inline]
pub fn unescape_newline(s: &str) -> Cow<'_, str> {
    if s.contains("/n") {
        Cow::Owned(s.replace("/n", "\n"))
    } else {
        Cow::Borrowed(s)
    }
}
