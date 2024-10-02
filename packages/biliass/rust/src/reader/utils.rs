pub fn filter_bad_chars(string: &str) -> String {
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
        .collect()
}

pub fn calculate_length(s: &str) -> f32 {
    s.split('\n')
        .map(|line| line.chars().count())
        .max()
        .unwrap_or(0) as f32
}

pub fn unescape_newline(s: &str) -> String {
    s.replace("/n", "\n")
}
