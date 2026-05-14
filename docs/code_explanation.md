# Code Explanation

This document breaks down the logic within the primary files of the extension.

## 1. Extension Manifest (`extension.toml`)

This file registers the extension with Zed.

```toml
[slash_commands.paste-image]
description = "Paste an image from the clipboard into the current file"
requires_argument = false
```

- `requires_argument = false`: This allows the command to be run as an autocomplete option immediately upon typing `/`.

## 2. Main logic (`src/lib.rs`)

The Rust code implements the `zed::Extension` trait.

### `run_slash_command`
This is the entry point when a user triggers `/paste-image`. It dispatches to `paste_image_command`.

### `paste_image_command`
1.  **Worktree Context**: It retrieves the `root_path()` of the current workspace to determine where to save the `assets/` folder.
2.  **Sidecar Execution**:
    ```rust
    let output = Command::new("python3")
        .arg(script_path)
        .arg(&output_path)
        .output()?;
    ```
    It spawns `python3` with the path to our sidecar script and the target destination.
3.  **Result Handling**:
    - **Some(0)**: Successful execution. The WASM code generates the Markdown string.
    - **Some(1)**: Clipboard empty.
    - **Some(2)**: Missing platform dependencies.
4.  **Formatting**: The final result is returned as a `SlashCommandOutput`, which Zed's Assistant panel renders as clickable or editable text.

## 3. Sidecar Script (`scripts/paste_to_editor.py`)

The Python script uses standard libraries and sub-processes to interface with the host OS.

### Clipboard Drivers
- **wl-paste**: Checks Wayland clipboard.
- **xclip**: Checks X11 clipboard.
- **Pillow (ImageGrab)**: Uses the cross-platform Imaging Library.

### Logic Flow
1. Detect Operating System (`platform.system()`).
2. If Linux, determine if Wayland is active (`WAYLAND_DISPLAY`).
3. Attempt to capture PNG data.
4. If successful, binary data is written directly to the path provided by the extension.
