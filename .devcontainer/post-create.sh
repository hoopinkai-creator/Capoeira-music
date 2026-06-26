#!/usr/bin/env bash
# Provision a fresh dev container / Codespace for the Capoeira Music pipeline.
# Installs the native deps and the full Python stack into the container's system
# Python so `capoeira` is on PATH in every terminal (no venv activation needed).
set -euo pipefail

echo "==> Installing native dependencies (ffmpeg, libsndfile, cairo)..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg libsndfile1 libcairo2

echo "==> Installing capoeira-music with all extras..."
pip install --upgrade pip
pip install -e ".[all,dev]"

echo
echo "==> Environment check:"
capoeira status || true

echo
echo "Setup complete. Try:  capoeira process"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Tip: set an ANTHROPIC_API_KEY Codespaces secret to enable AI translation"
  echo "     (Settings -> Codespaces -> Secrets). Without it, the offline"
  echo "     glossary dictionary is used."
fi
