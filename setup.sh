#!/usr/bin/env bash
# One-shot setup for the Capoeira Music pipeline.
#
#   ./setup.sh            # create venv, install everything, verify
#   ./setup.sh --core     # core only (no audio/speech/ai/render extras)
#
# Re-running is safe: it reuses the existing virtual environment.
set -euo pipefail

cd "$(dirname "$0")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { printf "${GREEN}==>${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}!! ${NC} %s\n" "$1"; }
err()   { printf "${RED}xx ${NC} %s\n" "$1"; }

EXTRAS="[all,dev]"
[ "${1:-}" = "--core" ] && EXTRAS="[dev]"

# --- 1. Python -------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  err "python3 not found. Install Python 3.10+ first (https://www.python.org/downloads/)."
  exit 1
fi
PYVER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
info "Found Python $PYVER"

# --- 2. ffmpeg (needed to decode recordings) ------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
  info "ffmpeg already installed"
else
  warn "ffmpeg not found — it is required to decode recordings."
  if command -v brew >/dev/null 2>&1; then
    info "Installing ffmpeg with Homebrew..."
    brew install ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then
    info "Installing ffmpeg with apt-get (may prompt for sudo)..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
  elif command -v winget >/dev/null 2>&1; then
    info "Installing ffmpeg with winget..."
    winget install ffmpeg
  else
    warn "Could not auto-install ffmpeg. Install it manually, then re-run."
    warn "  macOS:   brew install ffmpeg"
    warn "  Debian:  sudo apt-get install ffmpeg"
    warn "  Windows: winget install ffmpeg"
  fi
fi

# --- 3. Virtual environment ------------------------------------------------
if [ ! -d .venv ]; then
  info "Creating virtual environment in .venv/"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
info "Using $(python --version) from $(command -v python)"

# --- 4. Install the package + extras --------------------------------------
info "Upgrading pip..."
python -m pip install --upgrade pip >/dev/null
info "Installing capoeira-music$EXTRAS (this can take a few minutes the first time)..."
pip install -e ".$EXTRAS"

# --- 5. Verify -------------------------------------------------------------
echo
info "Setup complete. Environment check:"
echo
capoeira status

echo
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  warn "ANTHROPIC_API_KEY is not set — Portuguese->English translation will use the"
  warn "offline dictionary fallback. To enable AI translation:"
  warn "  export ANTHROPIC_API_KEY=sk-ant-...   (add to ~/.zshrc to make it permanent)"
fi
echo
info "Next steps:"
echo "  1. Activate the environment in new terminals:  source .venv/bin/activate"
echo "  2. Make a class folder:                        recordings/2026-06-26-angola/"
echo "  3. Drop your Voice Memo(s) into it, then run:  capoeira process"
echo "  4. (Recommended) calibrate the classifier:     capoeira calibrate extract <class>"
