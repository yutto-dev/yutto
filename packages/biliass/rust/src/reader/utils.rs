use std::borrow::Cow;

/// Filter out bad control characters. Returns Cow::Borrowed when no
/// replacements are needed (the common case), avoiding allocation.
pub fn filter_bad_chars(string: &str) -> Cow<'_, str> {
    // Fast path: scan bytes to check if any bad chars exist
    let needs_filter = string.bytes().any(|b| {
        // Covers \u{00}-\u{08}, \u{0b}, \u{0c}, \u{0e}-\u{1f} (all single-byte in UTF-8)
        (b <= 0x08) || b == 0x0b || b == 0x0c || (0x0e..=0x1f).contains(&b)
    }) || string.contains('\u{2028}')
        || string.contains('\u{2029}');

    if !needs_filter {
        return Cow::Borrowed(string);
    }

    Cow::Owned(
        string
            .chars()
            .map(|c| {
                if ('\u{00}'..='\u{08}').contains(&c)
                    || c == '\u{0b}'
                    || c == '\u{0c}'
                    || c == '\u{2028}'
                    || c == '\u{2029}'
                    || ('\u{0e}'..='\u{1f}').contains(&c)
                {
                    '\u{fffd}'
                } else {
                    c
                }
            })
            .collect(),
    )
}

/// Calculate the display length of the longest line in a string.
/// Uses byte-level scanning for ASCII-heavy content.
pub fn calculate_length(s: &str) -> f32 {
    let mut max_len: usize = 0;
    let mut current_len: usize = 0;
    for c in s.chars() {
        if c == '\n' {
            if current_len > max_len {
                max_len = current_len;
            }
            current_len = 0;
        } else {
            current_len += 1;
        }
    }
    if current_len > max_len {
        max_len = current_len;
    }
    max_len as f32
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
