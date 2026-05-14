#!/usr/bin/env bash
# =============================================================================
#  update.sh — zed-file-drop extension updater
#
#  Run this any time you change src/lib.rs or extension.toml.
#  It will:
#    1. Build the WASM extension (cargo build --release --target wasm32-wasip1)
#    2. Build the sidecar binary for the host machine
#    3. Copy the extension.wasm + sidecar binary into Zed's installed directory
#    4. Optionally restart Zed so the changes are picked up immediately
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# Icons (Nerd Font)
ICON_INFO="󰋽"
ICON_SUCCESS="󰄬"
ICON_WARN="󰀪"
ICON_ERROR="󰅙"
ICON_SYNC="󰓦"
ICON_RESTART="󰜉"

info()    { echo -e "${CYAN}${BOLD}${ICON_INFO}${RESET}  $*"; }
success() { echo -e "${GREEN}${BOLD}${ICON_SUCCESS}${RESET}  $*"; }
warn()    { echo -e "${YELLOW}${BOLD}${ICON_WARN}${RESET}  $*"; }
error()   { echo -e "${RED}${BOLD}${ICON_ERROR}${RESET}  $*" >&2; }
sync()    { echo -e "${CYAN}${BOLD}${ICON_SYNC}${RESET}  $*"; }
restart() { echo -e "${YELLOW}${BOLD}${ICON_RESTART}${RESET}  $*"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_ID="zed-file-drop"
ZED_EXTENSIONS_DIR="${HOME}/.local/share/zed/extensions/installed/${EXTENSION_ID}"
WASM_TARGET="wasm32-wasip1"
WASM_SRC="${SCRIPT_DIR}/target/${WASM_TARGET}/release/zed_file_drop.wasm"
WASM_DST="${ZED_EXTENSIONS_DIR}/extension.wasm"
SIDECAR_NAME="zed-file-drop-sidecar"
SIDECAR_SRC="${SCRIPT_DIR}/target/release/${SIDECAR_NAME}"
SIDECAR_DST="${ZED_EXTENSIONS_DIR}/${SIDECAR_NAME}"

echo ""
echo -e "${CYAN}${BOLD}󰋩  zed-file-drop ${RESET}${CYAN}· Update Script${RESET}"
echo -e "${CYAN}──────────────────────────────────────────────────${RESET}"
echo ""

# ── Step 1: Verify we're in the right directory ───────────────────────────────
info "Project root: ${SCRIPT_DIR}"

if [[ ! -f "${SCRIPT_DIR}/Cargo.toml" ]]; then
  error "Cargo.toml not found. Run this script from the project root."
  exit 1
fi

# ── Step 2: Ensure wasm32-wasip1 target is installed ─────────────────────────
if ! rustup target list --installed 2>/dev/null | grep -q "${WASM_TARGET}"; then
  info "WASM target not installed. Adding ${WASM_TARGET}…"
  rustup target add "${WASM_TARGET}"
fi

# ── Step 3: Build WASM extension ──────────────────────────────────────────────
info "Building WASM extension…"
cd "${SCRIPT_DIR}"
cargo build --release --target "${WASM_TARGET}" 2>&1

if [[ ! -f "${WASM_SRC}" ]]; then
  error "Build succeeded but WASM file not found at: ${WASM_SRC}"
  exit 1
fi

success "Build complete → $(du -sh "${WASM_SRC}" | cut -f1) WASM"

# ── Step 4: Build sidecar for host machine ────────────────────────────────────
info "Building sidecar binary…"
cargo build --release -p "${EXTENSION_ID}" --bin "${SIDECAR_NAME}" 2>&1

if [[ ! -f "${SIDECAR_SRC}" ]]; then
  error "Sidecar build succeeded but binary not found at: ${SIDECAR_SRC}"
  exit 1
fi

success "Sidecar build complete → $(du -sh "${SIDECAR_SRC}" | cut -f1)"

# ── Step 5: Sync files to Zed ──────────────────────────────────────────────────
if [[ "$(realpath "${SCRIPT_DIR}")" == "$(realpath "${ZED_EXTENSIONS_DIR}")" ]]; then
  info "Source and destination are the same folder (dev extension). Skipping sync..."
else
  if [[ ! -d "${ZED_EXTENSIONS_DIR}" ]]; then
    warn "Installed extension dir not found: ${ZED_EXTENSIONS_DIR}"
    warn "Make sure you've installed 'zed-file-drop' via Zed's extension manager first."
    exit 1
  fi

  sync "Syncing extension files to Zed…"

  # Copy the freshly built WASM
  cp "${WASM_SRC}" "${WASM_DST}"
  success "Copied extension.wasm"

  # Copy the sidecar binary
  cp "${SIDECAR_SRC}" "${SIDECAR_DST}"
  success "Copied ${SIDECAR_NAME}"

  # Copy extension.toml
  cp "${SCRIPT_DIR}/extension.toml" "${ZED_EXTENSIONS_DIR}/extension.toml"

  success "Synced extension.wasm + sidecar + extension.toml"
fi

# Also keep the local copies up to date
cp "${WASM_SRC}" "${SCRIPT_DIR}/extension.wasm"
cp "${SIDECAR_SRC}" "${SCRIPT_DIR}/${SIDECAR_NAME}"
success "Updated project-root extension.wasm and sidecar"

# ── Step 6: Optionally restart Zed ───────────────────────────────────────────
echo ""
if pgrep -x "zed" > /dev/null; then
  read -rp "$(echo -e "${YELLOW}Zed is running. Restart it to apply changes? [Y/n]: ${RESET}")" answer
  answer="${answer:-Y}"
  if [[ "${answer}" =~ ^[Yy]$ ]]; then
    restart "Restarting Zed…"
    pkill -x zed || true
    sleep 1
    nohup zed . > /dev/null 2>&1 &
    success "Zed restarted!"
  else
    warn "Skipped. Reload the extension manually via: Extensions → zed-file-drop → Reload"
  fi
else
  info "Zed is not running. Start it normally — the updated extension will load automatically."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo -e "${CYAN}──────────────────────────────────────────────────${RESET}"
echo -e "${GREEN}${BOLD}${ICON_SUCCESS}  zed-file-drop updated successfully!${RESET}"
echo ""