fn divmod(a: f64, b: f64) -> (f64, f64) {
    (a / b, a % b)
}

pub fn convert_timestamp(timestamp: f64) -> String {
    let timestamp = (timestamp * 100.0).round();
    let (hour, minute) = divmod(timestamp, 360000.0);
    let (minute, second) = divmod(minute, 6000.0);
    let (second, centsecond) = divmod(second, 100.0);
    let hour = hour as u32;
    let minute = minute as u32;
    let second = second as u32;
    let centsecond = centsecond as u32;

    format!("{}:{:02}:{:02}.{:02}", hour, minute, second, centsecond)
}
