use rustc_hash::FxHashMap;
use std::sync::{Mutex, OnceLock};
use tracing::warn;

// Type aliases for better readability
type SourceSize = (u32, u32);
type TargetSize = (u32, u32);
type ZoomResult = (f32, f32, f32);
type ZoomKey = (SourceSize, TargetSize);

/// High-performance cache for zoom factor calculations
struct ZoomFactorCache {
    cache: Mutex<FxHashMap<ZoomKey, ZoomResult>>,
}

impl ZoomFactorCache {
    fn new() -> Self {
        Self {
            cache: Mutex::new(FxHashMap::default()),
        }
    }

    fn get_or_compute<F>(&self, key: ZoomKey, compute_fn: F) -> ZoomResult
    where
        F: FnOnce() -> ZoomResult,
    {
        let mut cache = self.cache.lock().unwrap();
        *cache.entry(key).or_insert_with(compute_fn)
    }
}

static ZOOM_CACHE: OnceLock<ZoomFactorCache> = OnceLock::new();

fn get_cache() -> &'static ZoomFactorCache {
    ZOOM_CACHE.get_or_init(ZoomFactorCache::new)
}

fn compute_zoom_factor(source_size: SourceSize, target_size: TargetSize) -> ZoomResult {
    let source_size_f = (source_size.0 as f32, source_size.1 as f32);
    let target_size_f = (target_size.0 as f32, target_size.1 as f32);
    let source_aspect = source_size_f.0 / source_size_f.1;
    let target_aspect = target_size_f.0 / target_size_f.1;

    if target_aspect < source_aspect {
        // narrower
        let scale_factor = target_size_f.0 / source_size_f.0;
        (
            scale_factor,
            0.0,
            (target_size_f.1 - target_size_f.0 / source_aspect) / 2.0,
        )
    } else if target_aspect > source_aspect {
        // wider
        let scale_factor = target_size_f.1 / source_size_f.1;
        (
            scale_factor,
            (target_size_f.0 - target_size_f.1 * source_aspect) / 2.0,
            0.0,
        )
    } else {
        (target_size_f.0 / source_size_f.0, 0.0, 0.0)
    }
}

/// Public interface for getting zoom factor with caching
pub fn get_zoom_factor(source_size: SourceSize, target_size: TargetSize) -> ZoomResult {
    let key = (source_size, target_size);
    get_cache().get_or_compute(key, || compute_zoom_factor(source_size, target_size))
}

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

    format!("{hour}:{minute:02}:{second:02}.{centsecond:02}")
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
        format!("{b:02X}{g:02X}{r:02X}")
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

// Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
//                      and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
// ASS FOV = width*4/3.0
// But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
// Result: (trans_x, trans_y, rot_x, rot_y, rot_z, scale_x, scale_y)
pub fn convert_flash_rotation(
    rot_y: f64,
    rot_z: f64,
    x: f64,
    y: f64,
    width: f64,
    height: f64,
) -> (f64, f64, f64, f64, f64, f64, f64) {
    let wrap_angle = |deg: f64| -> f64 { 180.0 - ((180.0 - deg).rem_euclid(360.0)) };
    let mut rot_y = wrap_angle(rot_y);
    let rot_z = wrap_angle(rot_z);
    let pi_angle = std::f64::consts::PI / 180.0;
    if rot_y == 90.0 || rot_y == -90.0 {
        rot_y -= 1.0;
    }
    let (out_x, out_y, out_z, rot_y, rot_z) = if rot_y == 0. || rot_z == 0. {
        let out_x = 0.;
        let out_y = -rot_y; // Positive value means clockwise in Flash
        let out_z = -rot_z;
        let rot_y_rad = rot_y * pi_angle;
        let rot_z_rad = rot_z * pi_angle;
        (out_x, out_y, out_z, rot_y_rad, rot_z_rad)
    } else {
        let rot_y_rad = rot_y * pi_angle;
        let rot_z_rad = rot_z * pi_angle;
        let out_y = (-rot_y_rad.sin() * rot_z_rad.cos()).atan2(rot_y_rad.cos()) / pi_angle;
        let out_z = (-rot_y_rad.cos() * rot_z_rad.sin()).atan2(rot_z_rad.cos()) / pi_angle;
        let out_x = (rot_y_rad.sin() * rot_z_rad.sin()).asin() / pi_angle;
        (out_x, out_y, out_z, rot_y_rad, rot_z_rad)
    };
    let trans_x = (x * rot_z.cos() + y * rot_z.sin()) / rot_y.cos()
        + (1.0 - rot_z.cos() / rot_y.cos()) * width / 2.0
        - rot_z.sin() / rot_y.cos() * height / 2.0;
    let trans_y = y * rot_z.cos() - x * rot_z.sin()
        + rot_z.sin() * width / 2.0
        + (1.0 - rot_z.cos()) * height / 2.0;
    let trans_z = (trans_x - width / 2.0) * rot_y.sin();
    let fov = width * (2.0 * std::f64::consts::PI / 9.0).tan() / 2.0;
    let scale_xy = if fov + trans_z != 0.0 {
        fov / (fov + trans_z)
    } else {
        warn!(
            "Rotation makes object behind the camera: trZ == {:.0}",
            trans_z
        );
        1.
    };
    let trans_x = (trans_x - width / 2.0) * scale_xy + width / 2.0;
    let trans_y = (trans_y - height / 2.0) * scale_xy + height / 2.0;
    let (scale_xy, out_x, out_y) = if scale_xy < 0. {
        warn!(
            "Rotation makes object behind the camera: trZ == {:.0} < {:.0}",
            trans_z, fov
        );
        (-scale_xy, out_x + 180., out_y + 180.)
    } else {
        (scale_xy, out_x, out_y)
    };
    (
        trans_x,
        trans_y,
        wrap_angle(out_x),
        wrap_angle(out_y),
        wrap_angle(out_z),
        scale_xy * 100.,
        scale_xy * 100.,
    )
}
