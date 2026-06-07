#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -U pip
pip install -e .

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo
  echo "ffmpeg was not found."
  echo "If Homebrew is installed, run: brew install ffmpeg"
  echo "Then run this installer again."
  exit 1
fi

mkdir -p downloads

echo
echo "Installed successfully."
echo "Run: ./douyin-download"
