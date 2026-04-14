#!/usr/bin/env python3
"""
paste_image.py — sidecar helper for the zed-file-drop extension.

Usage:
    python3 paste_image.py <output_path>

Exit codes:
    0  — image written to <output_path> successfully
    1  — no image found on clipboard
    2  — dependency missing (Pillow / wl-paste / xclip not found)
    3  — other error (message on stderr)

Cross-platform strategy:
    Linux (Wayland)  → wl-paste --type image/png
    Linux (X11)      → xclip -selection clipboard -t image/png -o
    macOS            → Pillow (PIL) ImageGrab
    Windows          → Pillow (PIL) ImageGrab
"""

import sys
import os
import subprocess
import platform

def main():
    if len(sys.argv) != 2:
        print("Usage: paste_image.py <output_path>", file=sys.stderr)
        sys.exit(3)

    output_path = sys.argv[1]
    os_name = platform.system()

    # ── Linux ─────────────────────────────────────────────────────────────────
    if os_name == "Linux":
        wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        if wayland:
            success = try_wl_paste(output_path)
        else:
            success = try_xclip(output_path)

        # Fallback: try the other tool if the primary one failed / not found
        if not success and wayland:
            success = try_xclip(output_path)
        if not success and not wayland:
            success = try_wl_paste(output_path)

        # Last-resort: Pillow
        if not success:
            success = try_pillow(output_path)

        sys.exit(0 if success else 1)

    # ── macOS / Windows ───────────────────────────────────────────────────────
    else:
        if not try_pillow(output_path):
            sys.exit(1)
        sys.exit(0)


def try_wl_paste(output_path: str) -> bool:
    """Use wl-paste (wl-clipboard) to grab a PNG from the clipboard."""
    try:
        result = subprocess.run(
            ["wl-paste", "--type", "image/png"],
            capture_output=True,
        )
        if result.returncode != 0 or not result.stdout:
            return False
        _write(output_path, result.stdout)
        return True
    except FileNotFoundError:
        return False


def try_xclip(output_path: str) -> bool:
    """Use xclip to grab a PNG image from the clipboard."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
            capture_output=True,
        )
        if result.returncode != 0 or not result.stdout:
            return False
        _write(output_path, result.stdout)
        return True
    except FileNotFoundError:
        return False


def try_pillow(output_path: str) -> bool:
    """Use Pillow's ImageGrab to read the clipboard (macOS/Windows, or Linux with X11)."""
    try:
        from PIL import ImageGrab  # type: ignore
    except ImportError:
        print("Pillow not installed. Run: pip install Pillow", file=sys.stderr)
        return False

    try:
        img = ImageGrab.grabclipboard()
        if img is None:
            return False
        # grabclipboard() can return a list of file paths on some platforms
        if isinstance(img, list):
            return False
        img.save(output_path, format="PNG")
        return True
    except Exception as e:
        print(f"Pillow error: {e}", file=sys.stderr)
        return False


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
