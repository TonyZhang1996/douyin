# Douyin Video Downloader

A small open-source CLI to download Douyin videos by URL, powered by `yt-dlp`.

## Install

### Option A: pip (editable)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
```

### Option B: pip (normal)

```powershell
pip install .
```

## Usage

```powershell
douyin-dl "<douyin_share_or_page_url>"
```

If the best format is separate video+audio streams, `yt-dlp` may require `ffmpeg` to merge them.

Download to a custom folder:

```powershell
douyin-dl "<url>" -o downloads
```

If a link fails (common for region/login/anti-bot), try cookies:

1. Export cookies to a `cookies.txt` file (Netscape format) from your browser.
2. Run:

```powershell
douyin-dl "<url>" --cookies .\cookies.txt
```

Or load cookies directly from your browser profile:

```powershell
douyin-dl "<url>" --cookies-from-browser edge
```

If Douyin blocks `yt-dlp` even with cookies (common), use the CDP mode (drives a real browser profile and captures the detail JSON):

```powershell
douyin-dl "<url>" --via-cdp edge
```

## Notes

- This project is intended for personal learning/research. Please respect local laws and Douyin's Terms of Service.
- Download success depends on link type, region, account/login state, and Douyin anti-scraping rules.

## License

MIT. See `LICENSE`.
