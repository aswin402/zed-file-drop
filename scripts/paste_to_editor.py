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

CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"

def dim(text: str) -> str:
    return f"\033[2m{text}{CLR_RESET}"

def bright(text: str) -> str:
    return f"\033[0m{text}{CLR_RESET}"

def box(lines: list[str], width: int = 48):
    """Draw a centered text box."""
    print()
    print(f"  ┌{'─' * (width - 2)}┐")
    for line in lines:
        pad = width - 4 - len(_strip_ansi(line))
        print(f"  │{_strip_ansi(line):^{width - 4}}{' ' * max(0, pad)}│")
    print(f"  └{'─' * (width - 2)}┘")

def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def ok(text: str):
    print(f"  {dim('●')} {text}")

def info(text: str):
    print(f"  {dim('○')} {text}")


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
    results = None

    if os_name == "Linux":
        if wayland:
            results = try_wayland(assets_dir, timestamp)
        if not results:
            results = try_x11(assets_dir, timestamp)

    # macOS / Windows fallback (and Linux last-resort)
    if not results:
        results = try_pillow(assets_dir, timestamp)

    if not results:
        box([
            dim("━━━"),
            "No image or file found",
            "",
            dim("Copy something first, then retry"),
            dim("━━━"),
        ])
        sys.exit(1)

    all_md_links = []

    for dest_path, filename, is_image in results:
        if is_image:
            md_link = f"![](assets/{filename})"
        else:
            md_link = f"[{filename}](assets/{filename})"

        all_md_links.append(md_link)
        ok(f"assets/{filename}")
        info(md_link)

    # ── Write the markdown link back to clipboard so user can Ctrl+V ─────────
    final_text = "\n".join(all_md_links)
    write_to_clipboard(final_text, wayland)

    print()
    info(f"Paste with {dim('Ctrl+V')}")
    print()

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
                    return [(dest, filename, True)]

        # Priority 2: file:// URIs (Nautilus, Thunar, etc.)
        for uri_mime in ("text/uri-list", "x-special/gnome-copied-files"):
            if uri_mime in available:
                uri_r = subprocess.run(["wl-paste", "--type", uri_mime], capture_output=True, text=True)
                if uri_r.returncode == 0 and uri_r.stdout.strip():
                    results = _handle_uri_list(uri_r.stdout, assets_dir, timestamp)
                    if results:
                        return results

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
            return [(dest, filename, True)]

        # Priority 2: file:// URIs
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            results = _handle_uri_list(r.stdout, assets_dir, timestamp)
            if results:
                return results

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
            results = []
            for path_str in img:
                p = Path(str(path_str))
                if p.exists():
                    results.append(_safe_copy(p, assets_dir, timestamp))
            return results if results else None

        # It's a PIL Image object (screenshot / copied image)
        filename = f"image-{timestamp}.png"
        dest = assets_dir / filename
        img.save(dest, format="PNG")
        return [(dest, filename, True)]

    except ImportError:
        return None
    except Exception as e:
        pass  # Best-effort


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

def _safe_copy(source_path: Path, assets_dir: Path, timestamp: str) -> tuple[Path, str, bool]:
    """Copy a file or directory safely to assets_dir, avoiding collisions."""
    filename = source_path.name
    dest = assets_dir / filename
    
    if dest.exists():
        filename = f"{source_path.stem}-{timestamp}{source_path.suffix}"
        dest = assets_dir / filename
        
    is_img = source_path.suffix.lower() in IMAGE_EXTENSIONS
    
    if source_path.is_dir():
        shutil.copytree(source_path, dest)
        is_img = False
    else:
        shutil.copy2(source_path, dest)
        
    return (dest, filename, is_img)


def _handle_uri_list(uri_text: str, assets_dir: Path, timestamp: str):
    """
    Parse a text/uri-list payload (newline-separated file:// URIs)
    and copy all items found into assets_dir.
    """
    lines = [l.strip() for l in uri_text.splitlines() if l.strip() and not l.startswith("#")]
    results = []

    for line in lines:
        # Nautilus prefixes with "copy\n" for x-special/gnome-copied-files
        if not line.startswith("file://"):
            continue

        raw_path = urlparse(line).path
        file_path = Path(unquote(raw_path))

        if not file_path.exists():
            continue

        res = _safe_copy(file_path, assets_dir, timestamp)
        results.append(res)

    return results if results else None


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
