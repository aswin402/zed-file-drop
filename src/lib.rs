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
/// Uses a Rust sidecar binary to access the clipboard (WASM sandbox has no
/// direct clipboard access). The sidecar is spawned as a subprocess and:
///   - Creates <root>/assets/ if needed
///   - Saves the image/file with a timestamped name
///   - Outputs the markdown link to stdout
fn paste_image_command(worktree: Option<&Worktree>) -> zed::Result<SlashCommandOutput> {
    // ── 1. Resolve workspace root ────────────────────────────────────────────
    let root = worktree
        .map(|wt| wt.root_path())
        .ok_or_else(|| "No workspace is open. Open a folder first.".to_string())?;

    // ── 2. Find the sidecar binary ──────────────────────────────────────────
    //
    // The sidecar is built as part of the workspace and placed in
    // sidecar/target/release/zed_file_drop_sidecar (or .exe on Windows)
    let extension_root = std::env::current_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| String::from("."));

    // Try various paths for the sidecar
    let sidecar_name = if cfg!(target_os = "windows") {
        "zed-file-drop-sidecar.exe"
    } else {
        "zed-file-drop-sidecar"
    };

    // The sidecar is placed alongside the extension (same directory)
    let sidecar_paths = [
        format!("{}/{}", extension_root, sidecar_name),
        format!("{}/target/release/{}", extension_root, sidecar_name),
        format!("{}/../target/release/{}", extension_root, sidecar_name),
    ];

    let sidecar_path = sidecar_paths
        .iter()
        .find(|p| std::path::Path::new(p).exists())
        .ok_or_else(|| "Sidecar binary not found. Please rebuild the project.".to_string())?
        .clone();

    // ── 3. Run the sidecar ───────────────────────────────────────────────────
    let output = Command::new(&sidecar_path)
        .arg(&root)
        .output()
        .map_err(|e| format!("Failed to run sidecar: {}", e))?;

    match output.status {
        // Success
        Some(0) => {
            let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let _stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

            // First line is typically the markdown link
            let md_link = stdout
                .lines()
                .next()
                .unwrap_or("")
                .trim()
                .to_string();

            // Check if we got a valid link
            if md_link.is_empty() {
                return Err("No output from sidecar".to_string());
            }

            let label = if md_link.contains("![") {
                "󰋩 Pasted image".to_string()
            } else {
                "󰋩 Pasted file".to_string()
            };

            let len = md_link.len();
            Ok(SlashCommandOutput {
                text: md_link,
                sections: vec![SlashCommandOutputSection {
                    range: (0_usize..len).into(),
                    label,
                }],
            })
        }

        // Exit 1 – no image on clipboard
        Some(1) => Ok(SlashCommandOutput {
            text: "󰅙 No file/image in clipboard.".to_string(),
            sections: vec![SlashCommandOutputSection {
                range: (0_usize..25).into(),
                label: "󰋩 paste-image".to_string(),
            }],
        }),

        // Exit 2 – missing dependency
        Some(2) => Err("Clipboard tool not found.\n\
             Linux Wayland: sudo apt install wl-clipboard\n\
             Linux X11:     sudo apt install xclip"
            .to_string()),

        // Exit 3 – bad arguments
        Some(3) => Err("Bad arguments passed to sidecar.".to_string()),

        // Any other exit code
        code => {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            Err(format!(
                "Sidecar exited with code {:?}\nstdout: {}\nstderr: {}",
                code, stdout, stderr
            ))
        }
    }
}

zed::register_extension!(FileDropExtension);