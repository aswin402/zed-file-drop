# Features & Highlights

The `zed-file-drop` extension enhances the Zed editor experience by providing a seamless way to handle image data from the clipboard, similar to the "Paste Image" functionalities found in VS Code and Obsidian.

## Core Features

- **Slash Command Integration**: Triggered via `/paste-image` in the Zed Assistant panel.
- **Automated Asset Management**: 
    - Automatically creates an `assets/` directory if it doesn't exist.
    - Saves images with unique timestamped filenames.
- **Markdown Insertion**: Instantly inserts standard Markdown image syntax (`![](assets/image-xxx.png)`) at the current cursor position.
- **Global Configuration**: Support for universal availability across all projects via `~/.config/zed/tasks.json`.
- **Developer Automation**: Includes an `update.sh` script for rapid rebuilding and syncing during development.
- **Cross-Platform Support**: Works across Linux (Wayland & X11), macOS, and Windows.

## Implementation Highlights

### 1. Robust Clipboard Detection
The extension uses a multi-layered approach to detect images:
- Primary tools for Linux (`wl-paste`, `xclip`) are preferred for performance.
- A Python-based fallback (`Pillow`) ensures standard clipboard access on macOS and Windows.

### 2. Sandbox Escape via Sidecar
Successfully navigated the WASM sandbox limitations by offloading system-level tasks to a controlled host script.

### 3. Integrated Diagnostics
The extension provides clear feedback if:
- No image is found on the clipboard.
- Required system dependencies (like `xclip` or `Pillow`) are missing.
- Workspace permissions (trust) are required to run the sidecar.

## Why this is useful
Standard Markdown workflows often involve:
1. Taking a screenshot.
2. Saving it to a folder.
3. Manually typing out the relative path in the editor.

This extension reduces that entire workflow to a single command.
