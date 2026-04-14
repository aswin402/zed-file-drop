#!/usr/bin/env python3
"""
paste_to_editor.py — Smart clipboard-to-Markdown image paster for Zed.

Usage:
    python3 paste_to_editor.py <workspace_root>

Handles two clipboard scenarios:
  1. Raw image data  — Screenshots, browser right-click "Copy Image"
  2. File URI list   — Files copied in Nautilus, Thunar, Nemo, etc.

What it does:
  - Detects what's on the clipboard (image bytes OR file path)
  - Copies / saves the image to <workspace_root>/assets/image-<ts>.ext
  - Writes the resulting Markdown link back to the clipboard
  - Prints the link to stdout

Exit codes:
    0  — success
    1  — no image or image file found on clipboard
    2  — required tool not installed
    3  — bad arguments / other error
"""

import sys
import os
import subprocess
import platform
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

# ── Constants ─────────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".ico"}

# ── Styling ───────────────────────────────────────────────────────────────────

# ANSI Color Codes
CLR_CYAN = "\033[0;36m"
CLR_GREEN = "\033[0;32m"
CLR_YELLOW = "\033[1;33m"
CLR_RED = "\033[0;31m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

# Icons (Nerd Font)
ICON_CAMERA = "󰋩"
ICON_CHECK = "󰄬"
ICON_CLIPBOARD = "󰅍"
ICON_INFO = "󰋽"
ICON_ERROR = "󰅙"

def style(text: str, color: str) -> str:
    return f"{color}{text}{CLR_RESET}"

def print_header(title: str):
    print(style(f"\n{ICON_CAMERA} {title}", CLR_CYAN + CLR_BOLD))
    print(style("─" * 45, CLR_CYAN))

def print_footer():
    print(style("─" * 45, CLR_CYAN))


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: paste_to_editor.py <workspace_root>", file=sys.stderr)
        sys.exit(3)

    workspace_root = Path(sys.argv[1]).resolve()
    assets_dir = workspace_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Unique timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:19]

    os_name = platform.system()
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))

    # ── Attempt clipboard reading in order of priority ────────────────────────
    result = None

    if os_name == "Linux":
        if wayland:
            result = try_wayland(assets_dir, timestamp)
        if not result:
            result = try_x11(assets_dir, timestamp)

    # macOS / Windows fallback (and Linux last-resort)
    if not result:
        result = try_pillow(assets_dir, timestamp)

    if not result:
        print(f"{style(ICON_ERROR, CLR_RED)}  {style('Error:', CLR_BOLD)} No image or image file found on clipboard.", file=sys.stderr)
        sys.exit(1)

    _dest_path, filename = result
    md_link = f"![](assets/{filename})"

    # ── Write the markdown link back to clipboard so user can Ctrl+V ─────────
    write_to_clipboard(md_link, wayland)

    # Also print it so Zed's task output panel shows it
    print_header("zed-file-drop")
    print(f"{style(ICON_CHECK, CLR_GREEN)}  {style('Saved:', CLR_BOLD):<10} assets/{filename}")
    print(f"{style(ICON_CLIPBOARD, CLR_CYAN)}  {style('Linked:', CLR_BOLD):<10} {md_link}")
    print_footer()
    print(f"{style(ICON_INFO, CLR_YELLOW)}  Press {style('Ctrl+V', CLR_BOLD)} to paste link into your editor.\n")

    sys.exit(0)


# ── Linux / Wayland ───────────────────────────────────────────────────────────

def try_wayland(assets_dir: Path, timestamp: str):
    """Try to grab image data or file URIs from the Wayland clipboard."""
    try:
        # List all formats currently on the clipboard
        r = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True)
        if r.returncode != 0:
            return None
        available = set(r.stdout.strip().splitlines())

        # Priority 1: raw image bytes
        for mime in ("image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"):
            if mime in available:
                img_r = subprocess.run(["wl-paste", "--type", mime], capture_output=True)
                if img_r.returncode == 0 and img_r.stdout:
                    ext = _mime_to_ext(mime)
                    filename = f"image-{timestamp}{ext}"
                    dest = assets_dir / filename
                    dest.write_bytes(img_r.stdout)
                    return dest, filename

        # Priority 2: file:// URIs (Nautilus, Thunar, etc.)
        for uri_mime in ("text/uri-list", "x-special/gnome-copied-files"):
            if uri_mime in available:
                uri_r = subprocess.run(["wl-paste", "--type", uri_mime], capture_output=True, text=True)
                if uri_r.returncode == 0 and uri_r.stdout.strip():
                    result = _handle_uri_list(uri_r.stdout, assets_dir, timestamp)
                    if result:
                        return result

    except FileNotFoundError:
        pass  # wl-paste not installed

    return None


# ── Linux / X11 ───────────────────────────────────────────────────────────────

def try_x11(assets_dir: Path, timestamp: str):
    """Try to grab image data or file URIs from the X11 clipboard."""
    try:
        # Priority 1: raw image PNG bytes
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
            capture_output=True,
        )
        if r.returncode == 0 and r.stdout and len(r.stdout) > 8:
            filename = f"image-{timestamp}.png"
            dest = assets_dir / filename
            dest.write_bytes(r.stdout)
            return dest, filename

        # Priority 2: file:// URIs
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            result = _handle_uri_list(r.stdout, assets_dir, timestamp)
            if result:
                return result

    except FileNotFoundError:
        pass  # xclip not installed

    return None


# ── macOS / Windows (Pillow) ──────────────────────────────────────────────────

def try_pillow(assets_dir: Path, timestamp: str):
    """Use Pillow's ImageGrab for macOS/Windows clipboard access."""
    try:
        from PIL import ImageGrab  # type: ignore
        img = ImageGrab.grabclipboard()

        if img is None:
            return None

        # On macOS Pillow can return a list of file paths
        if isinstance(img, list):
            for path_str in img:
                p = Path(str(path_str))
                if p.exists() and p.suffix.lower() in IMAGE_EXTENSIONS:
                    filename = f"image-{timestamp}{p.suffix.lower()}"
                    dest = assets_dir / filename
                    shutil.copy2(p, dest)
                    return dest, filename
            return None

        # It's a PIL Image object (screenshot / copied image)
        filename = f"image-{timestamp}.png"
        dest = assets_dir / filename
        img.save(dest, format="PNG")
        return dest, filename

    except ImportError:
        return None
    except Exception as e:
        print(f"Pillow error: {e}", file=sys.stderr)
        return None


# ── Clipboard Write ───────────────────────────────────────────────────────────

def write_to_clipboard(text: str, wayland: bool = False):
    """
    Write the generated markdown link back to the clipboard.
    After this runs, the user can simply press Ctrl+V to insert it.
    """
    encoded = text.encode()
    try:
        if wayland:
            subprocess.run(["wl-copy"], input=encoded, check=True)
            return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=encoded,
        )
        return
    except FileNotFoundError:
        pass

    # macOS / Windows
    try:
        from PIL import ImageGrab  # type: ignore
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass  # Best-effort


# ── Helpers ───────────────────────────────────────────────────────────────────

def _handle_uri_list(uri_text: str, assets_dir: Path, timestamp: str):
    """
    Parse a text/uri-list payload (newline-separated file:// URIs)
    and copy the first image file found into assets_dir.
    """
    lines = [l.strip() for l in uri_text.splitlines() if l.strip() and not l.startswith("#")]

    for line in lines:
        # Nautilus prefixes with "copy\n" for x-special/gnome-copied-files
        if not line.startswith("file://"):
            continue

        raw_path = urlparse(line).path
        file_path = Path(unquote(raw_path))

        if not file_path.exists():
            continue

        suffix = file_path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            continue

        filename = f"image-{timestamp}{suffix}"
        dest = assets_dir / filename
        shutil.copy2(file_path, dest)
        return dest, filename

    return None


def _mime_to_ext(mime: str) -> str:
    mapping = {
        "image/png":  ".png",
        "image/jpeg": ".jpg",
        "image/gif":  ".gif",
        "image/webp": ".webp",
        "image/bmp":  ".bmp",
    }
    return mapping.get(mime, ".png")


if __name__ == "__main__":
    main()
