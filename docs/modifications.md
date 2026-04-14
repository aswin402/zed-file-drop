# Development History & Modifications

This document tracks the significant changes and bug fixes made during the development of the `zed-file-drop` extension.

## Initial Concept
- Plan to use the `arboard` crate for direct Rust-based clipboard access.
- Target: `wasm32-wasip1`.

## Modification 1: Sandbox Constraints
- **Problem**: `arboard` failed to compile for WASM due to missing native OS libraries.
- **Solution**: Pivoted from a pure-Rust implementation to a **Sidecar Pattern**. Created `scripts/paste_image.py` to handle the platform-specific clipboard logic on the host machine.

## Modification 2: Type System Fixes
- **Problem**: Mismatched types in `run_slash_command`. `output.status` was an `Option<i32>`, but logic was matching against plain `i32`.
- **Solution**: Updated the `match` block to handle the `Option` enum (`Some(0)`) and the fallthrough case using debug formatting `{:?}`.

## Modification 3: Range Bounds
- **Problem**: Zed's `Range` type only implements `From` for `u32` and `usize`. Rust literals default to `i32`.
- **Solution**: Explicitly cast range literals to `usize` (e.g., `0_usize..len`) to satisfy the `zed_extension_api` requirements.

## Modification 4: Parent Workspace Conflict
- **Problem**: An empty `Cargo.toml` in the parent directory was causing build failures as Cargo tried to interpret the entire directory tree as a single (invalid) workspace.
- **Solution**: Created a valid root-level `Cargo.toml` that explicitly excludes the `zed-file-drop` directory, allowing it to maintain its own independent build settings and lockfile.

## Modification 5: Slash Command Naming
- **Problem**: Initial draft used `/insert-file`.
- **Solution**: Renamed to `/paste-image` to better reflect the specific functionality of the extension and avoid confusion with general file-picking commands.

## Modification 6: Global Task Support
- **Problem**: The snippet in `.zed/tasks.json` was project-specific. Users had to copy it into every new folder they opened.
- **Solution**: Added the task to the global Zed configuration at `~/.config/zed/tasks.json`. Updated the script path to be absolute, ensuring it works regardless of which project is open.

## Modification 7: Developer Automation Script
- **Problem**: Manually rebuilding the WASM extension and syncing files to Zed's internal `~/.local/share/zed/extensions` directory was tedious and error-prone during development.
- **Solution**: Created `update.sh`. This script automates the full cycle: 
    1.  Building the WASM blob for `wasm32-wasip1`.
    2.  Using `rsync` to sync only relevant scripts and metadata.
    3.  Restarting Zed (optional) to trigger an immediate extension reload.

## Modification 8: TUI Modernization (v0.2.0)
- **Problem**: The original terminal output relied heavily on standard emojis which sometimes rendered inconsistently across different terminal emulators and lacked a professional tool feel.
- **Solution**: Replaced standard emojis with consistent Nerd Font icons (e.g., `󰋩`, ``, ``, ``) and clean ASCII characters for bounding boxes and visual separation. This modernized the look and improved visual hierarchy in the command output.
