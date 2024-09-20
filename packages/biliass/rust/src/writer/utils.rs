use cached::proc_macro::cached;

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

pub fn ass_escape(text: &str) -> String {
    text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .split('\n')
        .map(|line| {
            let stripped = line.trim_matches(' ');
            let size = line.len();
            if stripped.len() == size {
                line.to_owned()
            } else {
                let leading_spaces = line.len() - line.trim_start_matches(' ').len();
                let trailing_spaces = line.len() - line.trim_end_matches(' ').len();
                format!(
                    "{}{}{}",
                    "\u{2007}".repeat(leading_spaces),
                    stripped,
                    "\u{2007}".repeat(trailing_spaces)
                )
            }
        })
        .collect::<Vec<_>>()
        .join("\\N")
}

pub fn convert_color(rgb: u32, width: Option<u32>, height: Option<u32>) -> String {
    let width = width.unwrap_or(1280);
    let height = height.unwrap_or(576);
    if rgb == 0x000000 {
        return "000000".to_owned();
    } else if rgb == 0xFFFFFF {
        return "FFFFFF".to_owned();
    }
    let r = (rgb >> 16) & 0xFF;
    let g = (rgb >> 8) & 0xFF;
    let b = rgb & 0xFF;
    if width < 1280 && height < 576 {
        format!("{:02X}{:02X}{:02X}", b, g, r)
    } else {
        format!(
            "{:02X}{:02X}{:02X}",
            (r as f64 * 0.009_563_840_880_806_56
                + g as f64 * 0.032_172_545_402_037_29
                + b as f64 * 0.958_263_613_717_156_1)
                .clamp(0.0, 255.0)
                .round() as u8,
            (r as f64 * -0.104_939_331_420_753_9
                + g as f64 * 1.172_314_781_918_551_5
                + b as f64 * -0.067_375_450_497_797_57)
                .clamp(0.0, 255.0)
                .round() as u8,
            (r as f64 * 0.913_489_123_739_876_5
                + g as f64 * 0.078_585_363_725_325_1
                + b as f64 * 0.007_925_512_534_798_42)
                .clamp(0.0, 255.0)
                .round() as u8,
        )
    }
}

#[cached]
pub fn get_zoom_factor(source_size: (u32, u32), target_size: (u32, u32)) -> (f32, f32, f32) {
    let source_size = (source_size.0 as f32, source_size.1 as f32);
    let target_size = (target_size.0 as f32, target_size.1 as f32);
    let source_aspect = source_size.0 / source_size.1;
    let target_aspect = target_size.0 / target_size.1;
    if target_aspect < source_aspect {
        // narrower
        let scale_factor = target_size.0 / source_size.0;
        (
            scale_factor,
            0.0,
            (target_size.1 - target_size.0 / source_aspect) / 2.0,
        )
    } else if target_aspect > source_aspect {
        // wider
        let scale_factor = target_size.1 / source_size.1;
        (
            scale_factor,
            (target_size.0 - target_size.1 * source_aspect) / 2.0,
            0.0,
        )
    } else {
        (target_size.0 / source_size.0, 0.0, 0.0)
    }
}
