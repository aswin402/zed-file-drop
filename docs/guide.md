# User Guide

This guide covers setup, installation, and practical usage of `zed-file-drop`.

---

## Prerequisites

### Python 3
Must be available as `python3` in your terminal:
```bash
python3 --version
```

### Platform clipboard tool

| Platform | Tool | Install |
|---|---|---|
| Linux (Wayland) | `wl-clipboard` | `sudo apt install wl-clipboard` |
| Linux (X11) | `xclip` | `sudo apt install xclip` |
| macOS / Windows | Pillow | `pip install Pillow` |

> The script auto-detects your environment. If you're on Wayland but also have xclip, both work — Wayland tools are tried first.

---

## Installation

### As a Dev Extension

1. Open **Zed**.
2. Open Command Palette: `Ctrl+Shift+P`
3. Run **`zed: install dev extension`**.
4. Select the `zed-file-drop/` directory.
5. Zed compiles the extension and registers it.

### Global Task Setup (Recommended)

To use "📸 Paste Image" in **any** project without copying configuration files everywhere, add it to your global Zed tasks:

1.  Open **`~/.config/zed/tasks.json`**.
2.  Paste the following:

```json
[
  {
    "label": "📸 Paste Image",
    "command": "python3",
    "args": [
      "/home/aswin/programming/vscode/myProjects/zed-file-drop/scripts/paste_to_editor.py",
      "${ZED_WORKTREE_ROOT}"
    ],
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "always"
  }
]
```

### Dev Workflow: update.sh

If you are modifying the extension code (`src/lib.rs` or Python scripts), you don't need to manually copy files. From the project root, run:

```bash
bash update.sh
```

This script handles the WASM compilation, file syncing, and (optionally) restarts Zed for you.


---

## Daily Usage

### The Two-Step Flow

This is the fastest, most reliable method:

1. **Copy** an image:
   - Take a screenshot
   - OR right-click an image in Nautilus → **Copy** (`Ctrl+C`)
   - OR right-click an image in Firefox → **Copy Image**

2. **In Zed**, run the task:
   - `Ctrl+Shift+P` → type **`task`** → select **📸 Paste Image**
   
![Selecting the Task](screenshots/select_paste_image.png)

   - OR press your custom hotkey (see below)

3. The terminal briefly shows:
   ```
   ✅ Image saved:  assets/image-20240414_103000.png
   📋 In clipboard: ![](assets/image-20240414_103000.png)
   ```

![Terminal Output Feedback](screenshots/searchtask.png)


4. **Place your cursor** in the editor and press `Ctrl+V`.

---

## Setting Up a Keyboard Shortcut

The fastest daily workflow is to bind the task to a key.

### Step 1 — Verify the task is registered

Open `Ctrl+Shift+P` → type `task` → confirm **📸 Paste Image** appears.

### Step 2 — Add keybinding

Open the keymap file: `Ctrl+Shift+P` → **`zed: open keymap`**.

Add:
```json
[
  {
    "context": "Workspace",
    "bindings": {
      "ctrl+shift+v": ["task::Spawn", { "task_name": "📸 Paste Image" }]
    }
  }
]
```

Now your workflow becomes:
- `Ctrl+C` (copy image in Nautilus)
- `Ctrl+Shift+V` (run Zed task)
- `Ctrl+V` (paste markdown link)

---

## Examples

### Example 1: Screenshot of a UI bug

1. Press `PrtSc` to take a screenshot (image goes to clipboard).
2. Switch to Zed, open `CHANGELOG.md`.
3. Press `Ctrl+Shift+V`.
4. Press `Ctrl+V` at the cursor.
5. Result: `![](assets/image-20240414_120001.png)` appears in your file.

### Example 2: Paste from Nautilus File Manager

1. Open Nautilus, navigate to your screenshots folder.
2. Click an image → `Ctrl+C`.
3. Switch to Zed, position cursor in `README.md`.
4. Press `Ctrl+Shift+V` → `Ctrl+V`.
5. Result: The file is **copied** to `assets/` in your project and a markdown link is inserted.

### Example 3: Copy image from the web

1. In Firefox, right-click any image → **Copy Image**.
2. Switch to Zed → `Ctrl+Shift+V` → `Ctrl+V`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No image or image file found on clipboard` | Make sure you used Copy Image, not Copy Image Link |
| Task not found in `task: spawn` | Check `~/.config/zed/tasks.json` has the correct path to `paste_to_editor.py` |
| `wl-paste: not found` | `sudo apt install wl-clipboard` |
| `xclip: not found` | `sudo apt install xclip` |
| Nothing written to assets/ | Check the workspace is a folder (not a single file) open in Zed |

