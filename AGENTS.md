# AGENTS.md — zed-file-drop

## Project Overview

A Zed editor extension + Python sidecar that pastes images/files from the clipboard into Markdown. The WASM extension provides a `/paste-image` slash command in the Assistant panel; the Python script provides the full workflow (saves file, copies markdown link back to clipboard).

**Two entry points exist:**
1. `/paste-image` — slash command in Assistant panel (Rust/WASM only)
2. Task `󰋩 Paste File/Image` — triggers Python sidecar directly (full workflow, saves image to `assets/` and copies markdown link to clipboard for Ctrl+V)

---

## Essential Commands

```bash
# Build WASM extension
cargo build --release --target wasm32-wasip1

# Development rebuild + sync to Zed's installed-extensions dir + optional restart
bash update.sh

# Output: target/wasm32-wasip1/release/zed_file_drop.wasm
```

---

## Architecture

### Sidecar Pattern
Zed extensions run in a `wasm32-wasip1` sandbox with **no direct clipboard access**. The workaround:
1. Rust extension spawns `python3 scripts/paste_to_editor.py <output_path>`
2. Python script reads the clipboard using platform tools
3. Python writes the image to disk
4. Rust generates the markdown link

### Clipboard Drivers (Python)
| Platform | Tool | Format |
|---|---|---|
| Linux Wayland | `wl-paste` | image/png, image/jpeg, text/uri-list |
| Linux X11 | `xclip` | image/png, text/uri-list |
| macOS/Windows | Pillow (`ImageGrab`) | images and file paths |

Detection: Check `WAYLAND_DISPLAY` env var → Wayland, else X11, else Pillow.

### Python Script Exit Codes
| Code | Meaning |
|---|---|
| 0 | Success — markdown link written to clipboard |
| 1 | No image/file on clipboard |
| 2 | Required tool not installed |
| 3 | Bad arguments |

### Rust Side
- `output.status` is `Option<i32>` — match with `Some(0)`, not plain `0`
- Range literals must be `usize` or `u32`: `(0_usize..len).into()`, not `(0..len)`
- WASM working directory = extension directory, so relative paths to `scripts/` work in dev

---

## File Structure

```
zed-file-drop/
├── Cargo.toml                 # WASM lib, crate-type = ["cdylib"]
├── extension.toml             # Zed manifest, registers /paste-image slash command
├── src/lib.rs                 # Extension entry, spawns Python sidecar
├── extension.wasm             # Built artifact (also at target/wasm32-wasip1/release/)
├── scripts/
│   └── paste_to_editor.py     # Main sidecar — clipboard read, file save, clipboard write
├── update.sh                  # Build + sync to ~/.local/share/zed/extensions/installed/
├── .zed/tasks.json            # Project-local task (not global)
├── docs/                      # Architecture, code explanation, features, modifications
└── assets/                    # Target directory for saved images
```

---

## Key Paths

- **Installed extension dir**: `~/.local/share/zed/extensions/installed/zed-file-drop/`
- **Global task config**: `~/.config/zed/tasks.json` (user must set this up manually)
- **Workspace root** (in Python): `Path(sys.argv[1]).resolve()` via `${ZED_WORKTREE_ROOT}`
- **Assets dir**: `<workspace_root>/assets/` (created automatically)

---

## Conventions & Patterns

- **WASM output filename**: `zed_file_drop.wasm` (cargo converts `zed-file-drop` to snake_case)
- **Image naming**: `image-<timestamp>.ext` where timestamp is `YYYYMMDD_HHMMSSffffff`
- **Markdown output**: `![](/assets/filename)` for images, `[filename](assets/filename)` for files
- **Nerd Font icons**: Used throughout (Python and bash scripts) — `󰋩`, `󰄬`, `󰅍`, etc.
- **Color codes**: ANSI escape sequences with `CLR_CYAN`, `CLR_GREEN`, `CLR_RED` etc.
- **Python retry**: 3 attempts with 0.3s delay for clipboard access timing issues

---

## Gotchas

1. **WASM sandbox cannot access clipboard directly** — always use the sidecar pattern
2. **Parent directory Cargo.toml** — an empty or misconfigured parent `Cargo.toml` will break the build by treating the project as a workspace
3. **`update.sh` skips sync if source=dest** — happens when Zed is running dev extension from project dir
4. **Rust Range requires `usize`/`u32`** — `0..len` fails, use `0_usize..len`
5. **`output.status` is `Option<i32>`** — match with `Some(0)` not plain `0`
6. **`extension.wasm` in project root must be kept updated** — `update.sh` copies it there
7. **Global task must be added manually** — `.zed/tasks.json` is project-local, user copies to `~/.config/zed/tasks.json`
8. **File URIs from file managers** — Nautilus/Thunar use `x-special/gnome-copied-files` format (prefixed with "copy\n"), not just `text/uri-list`
9. **`wl-paste --list-types` must be checked before `--type`** — if mime not available, the call fails silently
10. **Subdirectories synced with `--delete`** — `scripts/` and `docs/` are synced with rsync --delete, root-level files are copied individually

---

## Testing

- Manual: Run `bash update.sh`, restart Zed, invoke `/paste-image` or spawn task
- Verify clipboard is written back with markdown link
- Test on Wayland and X11 (Linux), check fallback order
- Test with image clipboard (screenshot) and file manager clipboard (file URI list)
- Test folder drop (files copied with `shutil.copytree`)

---

## Adding New Features

- **New slash command**: Add entry in `extension.toml` `[slash_commands.<name>]` and handle in `run_slash_command` match
- **New platform support**: Add detection in Python `main()`, add `try_<platform>()` function
- **Change markdown format**: Edit `md_link` generation in Python `main()`
- **Change storage location**: Update `assets_dir` in Python and `assets_dir` construction in Rust