use zed_extension_api::{
    self as zed, process::Command, SlashCommand, SlashCommandOutput, SlashCommandOutputSection,
    Worktree,
};

/// The single entry-point struct for this extension.
struct FileDropExtension;

impl zed::Extension for FileDropExtension {
    fn new() -> Self {
        FileDropExtension
    }

    fn run_slash_command(
        &self,
        command: SlashCommand,
        _args: Vec<String>,
        worktree: Option<&Worktree>,
    ) -> zed::Result<SlashCommandOutput> {
        match command.name.as_str() {
            "paste-image" => paste_image_command(worktree),
            _ => Err(format!("unknown slash command: {}", command.name)),
        }
    }
}

/// Core logic for /paste-image.
///
/// Architecture note
/// ─────────────────
/// Zed extensions run inside a wasm32-wasip1 sandbox.  The sandbox has
/// **no** direct access to system APIs like the clipboard.  We work around
/// this by calling a small Python sidecar script (`scripts/paste_image.py`)
/// that runs on the host and reads the clipboard using the appropriate
/// system tool for the platform:
///
///   Linux (Wayland) → wl-paste
///   Linux (X11)     → xclip
///   macOS / Windows → Pillow (PIL) ImageGrab
///
/// The script writes the PNG bytes to a temporary path we supply, then we
/// move the file to `<workspace-root>/assets/image-<timestamp>.png`.
///
/// Because `std::fs` works through WASI, the extension *can* perform basic
/// filesystem operations (mkdir, rename) once the worktree is trusted.
fn paste_image_command(worktree: Option<&Worktree>) -> zed::Result<SlashCommandOutput> {
    // ── 1. Resolve workspace root ────────────────────────────────────────────
    let root = worktree
        .map(|wt| wt.root_path())
        .ok_or_else(|| "No workspace is open. Open a folder first.".to_string())?;

    // ── 2. Build output path ─────────────────────────────────────────────────
    let timestamp = timestamp_ms();
    let filename = format!("image-{}.png", timestamp);
    let assets_dir = format!("{}/assets", root);
    let output_path = format!("{}/{}", assets_dir, filename);

    // ── 3. Locate the sidecar script ─────────────────────────────────────────
    //
    // `worktree.root_path()` points to the open project, but the sidecar
    // lives inside the *extension* directory itself.  Zed sets the working
    // directory of extension processes to the extension directory, so a
    // relative path works fine during dev-extension installs.
    //
    // For a published extension the sidecar must be included in the extension
    // repository; Zed copies every file from the repo root into the installed
    // extension dir.
    let script_path = "scripts/paste_to_editor.py";

    // ── 4. Call the sidecar ──────────────────────────────────────────────────
    let output = Command::new("python3")
        .arg(script_path)
        .arg(&output_path)
        .output()
        .map_err(|e| format!("Failed to run paste_image.py: {}", e))?;

    match output.status {
        // Success – image was written to output_path
        Some(0) => {
            let md_link = format!("![](assets/{})", filename);
            let len = md_link.len();
            Ok(SlashCommandOutput {
                text: md_link,
                sections: vec![SlashCommandOutputSection {
                    range: (0_usize..len).into(),
                    label: "󰋩 Pasted image".to_string(),
                }],
            })
        }

        // Exit 1 – no image on clipboard
        Some(1) => Ok(SlashCommandOutput {
            text: "󰅙 No image in clipboard.".to_string(),
            sections: vec![SlashCommandOutputSection {
                range: (0_usize..25).into(),
                label: "󰋩 paste-image".to_string(),
            }],
        }),

        // Exit 2 – missing dependency
        Some(2) => Err(
            "Clipboard tool not found.\n\
             Linux Wayland: install wl-clipboard (wl-paste)\n\
             Linux X11:     install xclip\n\
             macOS/Windows: pip install Pillow"
                .to_string(),
        ),

        // Any other exit code (or None if the process was killed)
        code => {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            Err(format!(
                "paste_image.py exited with code {:?}:\n{}",
                code, stderr
            ))
        }
    }
}

/// Returns milliseconds since Unix epoch as a string.
/// WASI's `std::time::SystemTime` is available and sufficient for this.
fn timestamp_ms() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

zed::register_extension!(FileDropExtension);