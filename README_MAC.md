# Douyin Video Downloader for macOS

## First-Time Setup

1. Install Google Chrome.
2. Install Python 3.
3. Install ffmpeg:

```bash
brew install ffmpeg
```

4. Open Terminal, enter this folder, then run:

```bash
chmod +x install_mac.sh douyin-download
./install_mac.sh
```

## Download A Video

Run:

```bash
./douyin-download
```

When prompted, paste a Douyin link or share text, then press Enter.

Downloaded videos are saved to:

```bash
downloads
```

## If A Video Fails

If you see `Fresh cookies` or `possible anti-bot/captcha`, open the link in Chrome first and confirm the video can play, then run `./douyin-download` again.
