use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;
use std::process::Command;
use std::time::SystemTime;

const IMAGE_EXTENSIONS: &[&str] = &[
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".ico",
];

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: zed-file-drop-sidecar <workspace_root>");
        std::process::exit(3);
    }

    let workspace_root = PathBuf::from(&args[1]);
    let assets_dir = workspace_root.join("assets");

    if let Err(e) = fs::create_dir_all(&assets_dir) {
        eprintln!("Failed to create assets directory: {}", e);
        std::process::exit(3);
    }

    let timestamp = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    let ts_string = format!("{}", timestamp.as_millis());

    // Try Wayland first
    if let Some(results) = try_wayland(&assets_dir, &ts_string) {
        output_results(&results);
        return;
    }

    // Try X11
    if let Some(results) = try_x11(&assets_dir, &ts_string) {
        output_results(&results);
        return;
    }

    // Try macOS/Windows
    if let Some(results) = try_pillow(&assets_dir, &ts_string) {
        output_results(&results);
        return;
    }

    eprintln!("No file or image found on clipboard.");
    std::process::exit(1);
}

fn output_results(results: &[(PathBuf, String, bool)]) {
    for (_dest, filename, is_image) in results {
        let md_link = if *is_image {
            format!("![](assets/{})", filename)
        } else {
            format!("[{}](assets/{})", filename, filename)
        };
        println!("{}", md_link);
        let _ = writeln!(io::stdout(), "Saved: assets/{}", filename);
    }
}

fn try_wayland(assets_dir: &PathBuf, timestamp: &str) -> Option<Vec<(PathBuf, String, bool)>> {
    let r = Command::new("wl-paste").arg("--list-types").output().ok()?;
    if r.status.code() != Some(0) {
        return None;
    }

    let available: std::collections::HashSet<String> = r
        .stdout
        .split(|&b| b == b'\n')
        .filter_map(|s| Some(String::from(String::from_utf8_lossy(s).trim())))
        .collect();

    // Try image types
    for mime in &["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"] {
        if available.contains(*mime) {
            let img_r = Command::new("wl-paste").arg("--type").arg(*mime).output().ok()?;
            if img_r.status.code() == Some(0) && !img_r.stdout.is_empty() {
                let ext = mime_to_ext(mime);
                let filename = format!("image-{}{}", timestamp, ext);
                let dest = assets_dir.join(&filename);
                if fs::write(&dest, &img_r.stdout).is_ok() {
                    return Some(vec![(dest, filename, true)]);
                }
            }
        }
    }

    // Try file URIs
    for uri_mime in &["text/uri-list", "x-special/gnome-copied-files"] {
        if available.contains(*uri_mime) {
            let uri_r = Command::new("wl-paste")
                .arg("--type")
                .arg(*uri_mime)
                .output()
                .ok()?;
            if uri_r.status.code() == Some(0) && !uri_r.stdout.is_empty() {
                if let Some(results) = handle_uri_list(&uri_r.stdout, assets_dir, timestamp) {
                    return Some(results);
                }
            }
        }
    }

    None
}

fn try_x11(assets_dir: &PathBuf, timestamp: &str) -> Option<Vec<(PathBuf, String, bool)>> {
    // Try image
    let r = Command::new("xclip")
        .args(["-selection", "clipboard", "-t", "image/png", "-o"])
        .output()
        .ok()?;
    if r.status.code() == Some(0) && r.stdout.len() > 8 {
        let filename = format!("image-{}.png", timestamp);
        let dest = assets_dir.join(&filename);
        if fs::write(&dest, &r.stdout).is_ok() {
            return Some(vec![(dest, filename, true)]);
        }
    }

    // Try file URIs
    let r = Command::new("xclip")
        .args(["-selection", "clipboard", "-t", "text/uri-list", "-o"])
        .output()
        .ok()?;
    if r.status.code() == Some(0) && !r.stdout.is_empty() {
        if let Some(results) = handle_uri_list(&r.stdout, assets_dir, timestamp) {
            return Some(results);
        }
    }

    None
}

fn try_pillow(_assets_dir: &PathBuf, _timestamp: &str) -> Option<Vec<(PathBuf, String, bool)>> {
    // For macOS/Windows, we could add PIL support here
    // For now, return None to let the extension handle it
    None
}

fn handle_uri_list(data: &[u8], assets_dir: &PathBuf, timestamp: &str) -> Option<Vec<(PathBuf, String, bool)>> {
    let text = String::from_utf8_lossy(data);
    let mut results = Vec::new();

    for line in text.split('\n') {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        // Handle x-special/gnome-copied-files format (starts with "copy\n" or "cut\n")
        let uri = if line.starts_with("copy\n") || line.starts_with("cut\n") {
            line.split('\n').nth(1).unwrap_or(line)
        } else {
            line
        };

        if !uri.starts_with("file://") {
            continue;
        }

        let path = url_decode(uri.strip_prefix("file://")?);
        let path = PathBuf::from(path);

        if !path.exists() {
            continue;
        }

        let filename = path.file_name()?.to_string_lossy().into_owned();
        let dest = assets_dir.join(&filename);

        // Handle collision
        let dest = if dest.exists() {
            let stem = path.file_stem()?.to_string_lossy();
            let ext = path.extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
            assets_dir.join(format!("{}-{}{}", stem, timestamp, ext))
        } else {
            dest
        };

        let is_image = path.extension()
            .map(|e| IMAGE_EXTENSIONS.contains(&e.to_string_lossy().to_lowercase().as_str()))
            .unwrap_or(false);

        if path.is_dir() {
            // Copy directory
            if copy_dir(&path, &dest).is_ok() {
                results.push((dest, filename, false));
            }
        } else if fs::copy(&path, &dest).is_ok() {
            results.push((dest, filename, is_image));
        }
    }

    if results.is_empty() {
        None
    } else {
        Some(results)
    }
}

fn copy_dir(src: &PathBuf, dst: &PathBuf) -> io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir(&entry.path(), &dst.join(entry.file_name()))?;
        } else {
            fs::copy(entry.path(), dst.join(entry.file_name()))?;
        }
    }
    Ok(())
}

fn url_decode(s: &str) -> String {
    let mut result = String::new();
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '%' {
            let hex: String = chars.by_ref().take(2).collect();
            if hex.len() == 2 {
                if let Ok(byte) = u8::from_str_radix(&hex, 16) {
                    result.push(byte as char);
                } else {
                    result.push('%');
                    result.push_str(&hex);
                }
            } else {
                result.push('%');
                result.push_str(&hex);
            }
        } else if c == '+' {
            result.push(' ');
        } else {
            result.push(c);
        }
    }
    result
}

fn mime_to_ext(mime: &str) -> &str {
    match mime {
        "image/png" => ".png",
        "image/jpeg" => ".jpg",
        "image/gif" => ".gif",
        "image/webp" => ".webp",
        "image/bmp" => ".bmp",
        _ => ".png",
    }
}