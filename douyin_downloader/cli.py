from __future__ import annotations

import argparse
import sys
from .downloader import (
    DownloadOptions,
    DouyinDownloaderError,
    download,
    extract_url,
    parse_cookies_from_browser,
)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="douyin-dl",
        description="Download a Douyin video by URL (powered by yt-dlp).",
    )
    p.add_argument(
        "text",
        nargs="+",
        help="Douyin share text or URL (we will extract the first http(s) URL if present)",
    )
    p.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Output directory (default: downloads)",
    )
    p.add_argument(
        "--filename",
        default="%(title).200B [%(id)s].%(ext)s",
        help="yt-dlp output template (default: %(default)s)",
    )
    p.add_argument(
        "--cookies",
        default=None,
        help="Path to cookies.txt exported from your browser (optional)",
    )
    p.add_argument(
        "--cookies-from-browser",
        default=None,
        help=(
            "Load cookies directly from your browser profile, e.g. 'chrome', 'edge', "
            "'firefox', or 'chrome:Default'. Format: BROWSER[+KEYRING][:PROFILE][::CONTAINER]"
        ),
    )
    p.add_argument(
        "--cookies-from-cdp",
        choices=["edge", "chrome"],
        default=None,
        help=(
            "Export cookies via DevTools Protocol by launching a temporary browser instance "
            "with your real profile. Useful when on-disk cookies are app-bound/encrypted and "
            "--cookies-from-browser fails."
        ),
    )
    p.add_argument(
        "--via-cdp",
        choices=["edge", "chrome"],
        default=None,
        help="Download by driving a real browser via CDP and capturing the detail JSON (highest success rate).",
    )
    p.add_argument("--cdp-port", type=int, default=9222, help="CDP port (default: 9222)")
    p.add_argument(
        "--cdp-profile",
        default="Default",
        help="Browser profile directory name (default: Default)",
    )
    p.add_argument(
        "--cdp-user-data-dir",
        default=None,
        help="Override browser User Data dir (advanced)",
    )
    p.add_argument(
        "--cdp-headless",
        action="store_true",
        help="Run CDP-launched browser in headless mode (may reduce success with anti-bot)",
    )
    p.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for yt-dlp, e.g. http://127.0.0.1:7890 (optional)",
    )
    p.add_argument(
        "--no-watermark",
        action="store_true",
        help="Prefer non-watermark formats if available (best-effort)",
    )
    p.add_argument(
        "--info-json",
        action="store_true",
        help="Also write info JSON next to the media file",
    )
    p.add_argument(
        "--audio-only",
        action="store_true",
        help="Download audio only (extract to m4a/mp3 depending on availability)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        out = download(
            DownloadOptions(
                text=" ".join(args.text),
                output=args.output,
                filename=args.filename,
                cookies=args.cookies,
                cookies_from_browser=args.cookies_from_browser,
                cookies_from_cdp=args.cookies_from_cdp,
                via_cdp=args.via_cdp,
                cdp_port=args.cdp_port,
                cdp_profile=args.cdp_profile,
                cdp_user_data_dir=args.cdp_user_data_dir,
                cdp_headless=bool(args.cdp_headless),
                proxy=args.proxy,
                no_watermark=bool(args.no_watermark),
                info_json=bool(args.info_json),
                audio_only=bool(args.audio_only),
            )
        )
        if out is not None:
            print(f"Saved: {out}")
        return 0
    except DouyinDownloaderError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
