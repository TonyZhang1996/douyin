param(
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

if ($Clean) {
  Remove-Item -Recurse -Force .\build, .\dist, .\*.spec -ErrorAction SilentlyContinue
}

python -m pip install -r .\requirements-dev.txt

pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name DouyinDownloaderGUI `
  --collect-all yt_dlp `
  .\douyin_downloader\gui.py

Write-Host ""
Write-Host "Build done: .\dist\DouyinDownloaderGUI.exe"

