from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.cookies import SUPPORTED_BROWSERS, SUPPORTED_KEYRINGS

from .cdp import (
    download_url_to_file,
    export_netscape_cookies_via_cdp,
    fetch_douyin_detail_json_via_cdp,
)


_TRAILING_PUNCT = ")]}>,.;:!?'\"，。；：！？、】【）】》…"


def extract_url(text: str) -> str | None:
    # Grab the first http(s) URL from share text.
    m = re.search(r"https?://\S+", text)
    if not m:
        return None
    url = m.group(0).strip()
    url = url.rstrip(_TRAILING_PUNCT)
    return url


def parse_cookies_from_browser(spec: str) -> tuple[str, str | None, str | None, str | None]:
    """
    Parse yt-dlp cookies-from-browser spec: BROWSER[+KEYRING][:PROFILE][::CONTAINER]
    Returns (browser_name, profile, keyring, container) where:
      - browser_name is lowercased
      - keyring is uppercased (if provided)
    """
    m = re.fullmatch(
        r"""(?x)
        (?P<name>[^+:]+)
        (?:\s*\+\s*(?P<keyring>[^:]+))?
        (?:\s*:\s*(?!:)(?P<profile>.+?))?
        (?:\s*::\s*(?P<container>.+))?
        """,
        spec.strip(),
    )
    if not m:
        raise ValueError(f"invalid --cookies-from-browser value: {spec!r}")

    name, keyring, profile, container = m.group("name", "keyring", "profile", "container")
    name = name.lower().strip()
    if name not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"unsupported browser for --cookies-from-browser: {name!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_BROWSERS))}"
        )

    if keyring is not None:
        keyring = keyring.upper().strip()
        if keyring not in SUPPORTED_KEYRINGS:
            raise ValueError(
                f"unsupported keyring for --cookies-from-browser: {keyring!r}. "
                f"Supported: {', '.join(sorted(map(str, SUPPORTED_KEYRINGS)))}"
            )

    if profile is not None:
        profile = profile.strip()
    if container is not None:
        container = container.strip()
        if container.lower() == "none":
            container = None

    return (name, profile, keyring, container)


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

    raw_text = " ".join(args.text).strip()
    url = extract_url(raw_text) or raw_text

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.via_cdp:
        # Browser-first method: use a real profile/session to bypass anti-bot that blocks raw HTTP.
        data = fetch_douyin_detail_json_via_cdp(
            browser=args.via_cdp,
            url=url,
            port=args.cdp_port,
            user_data_dir=args.cdp_user_data_dir,
            profile=args.cdp_profile,
            headless=bool(args.cdp_headless),
            timeout_s=90.0,
        )

        aweme = (data.get("aweme_detail") or data.get("awemeDetail") or {})
        desc = (aweme.get("desc") or "douyin").strip()
        aweme_id = str(aweme.get("aweme_id") or aweme.get("awemeId") or "video")
        video = aweme.get("video") or {}

        # Prefer play_addr URL list (usually non-watermark). Fallback to bit_rate variants.
        play = (video.get("play_addr") or video.get("playAddr") or {})
        url_list = play.get("url_list") or play.get("urlList") or []
        if not url_list:
            br = video.get("bit_rate") or video.get("bitRate") or []
            if br and isinstance(br, list):
                pa = (br[0].get("play_addr") or br[0].get("playAddr") or {})
                url_list = pa.get("url_list") or pa.get("urlList") or []

        if not url_list:
            print("ERROR: could not find playable URL in captured JSON (possible anti-bot/captcha)", file=sys.stderr)
            return 2

        media_url = url_list[0]
        safe = re.sub(r"[\\\\/:*?\"<>|]+", "_", desc)[:120].strip() or "douyin"
        out_path = out_dir / f"{safe} [{aweme_id}].mp4"
        download_url_to_file(media_url, out_path, user_agent=None, referer="https://www.douyin.com/")
        print(f"Saved: {out_path}")
        return 0

    ydl_opts: dict = {
        "outtmpl": str(out_dir / args.filename),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if args.cookies_from_cdp and (args.cookies or args.cookies_from_browser or args.via_cdp):
        print("ERROR: use only one of --cookies / --cookies-from-browser / --cookies-from-cdp", file=sys.stderr)
        return 2

    if args.cookies:
        ydl_opts["cookiefile"] = args.cookies
    if args.cookies_from_browser:
        if args.cookies:
            print("ERROR: use either --cookies or --cookies-from-browser (not both)", file=sys.stderr)
            return 2
        ydl_opts["cookiesfrombrowser"] = parse_cookies_from_browser(args.cookies_from_browser)
    if args.cookies_from_cdp:
        # Export to a temp cookies.txt via CDP, then let yt-dlp consume it.
        tmp_dir = Path(tempfile.mkdtemp(prefix="douyin-dl-"))
        tmp_cookies = tmp_dir / "cookies.txt"
        export_netscape_cookies_via_cdp(
            browser=args.cookies_from_cdp,
            url=url,
            out_path=tmp_cookies,
            port=args.cdp_port,
            user_data_dir=args.cdp_user_data_dir,
            profile=args.cdp_profile,
            headless=bool(args.cdp_headless),
        )
        ydl_opts["cookiefile"] = str(tmp_cookies)

    if args.proxy:
        ydl_opts["proxy"] = args.proxy

    if args.info_json:
        ydl_opts["writeinfojson"] = True

    # Formats: let yt-dlp decide best. Some sites expose watermark/non-watermark variants.
    # `--no-watermark` is best-effort by asking for best video+audio.
    if args.audio_only:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ]
    else:
        if args.no_watermark:
            ydl_opts["format"] = "bv*+ba/b"
        else:
            ydl_opts["format"] = "bestvideo*+bestaudio/best"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return 0
    except Exception as e:
        msg = str(e)
        print(f"ERROR: {msg}", file=sys.stderr)
        if "Could not copy Chrome cookie database" in msg:
            print(
                "Hint: yt-dlp failed to copy the Edge/Chrome cookie database.\n"
                "  - Fully close the browser (also background processes), then retry.\n"
                "    PowerShell: Get-Process msedge,chrome -ErrorAction SilentlyContinue | Stop-Process -Force\n"
                "  - Or export cookies to a Netscape cookies.txt and pass: --cookies .\\cookies.txt\n",
                file=sys.stderr,
            )
        elif "Failed to decrypt with DPAPI" in msg:
            print(
                "Hint: Your Chromium cookies may be app-bound/encrypted. Try:\n"
                "  - Export from DevTools (recommended here): --cookies-from-cdp edge\n"
                "  - Or export cookies.txt with a browser extension: --cookies .\\cookies.txt\n",
                file=sys.stderr,
            )
        elif "Fresh cookies" in msg or "cookies" in msg.lower():
            print(
                "Hint: Douyin often requires fresh cookies.\n"
                "  - Export cookies to a cookies.txt and pass: --cookies .\\cookies.txt\n"
                "  - Or load from browser: --cookies-from-browser edge (or chrome/firefox)\n"
                "  - Or export via CDP: --cookies-from-cdp edge\n",
                file=sys.stderr,
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
