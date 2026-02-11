param(
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

if ($Clean) {
  Remove-Item -Recurse -Force .\build, .\dist, .\*.spec -ErrorAction SilentlyContinue
}

python -m pip install -U pip
python -m pip install -e .
python -m pip install -r .\requirements-dev.txt

# Fail fast if runtime dependencies are missing in current interpreter.
python -c "import yt_dlp, websocket; print('deps ok')"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name DouyinDownloaderGUI `
  --hidden-import yt_dlp `
  --hidden-import yt_dlp.cookies `
  --hidden-import websocket `
  --collect-submodules yt_dlp `
  --collect-submodules websocket `
  .\douyin_downloader\gui.py

Write-Host ""
Write-Host "Build done: .\dist\DouyinDownloaderGUI.exe"
