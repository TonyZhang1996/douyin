from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from yt_dlp import YoutubeDL
from yt_dlp.cookies import SUPPORTED_BROWSERS, SUPPORTED_KEYRINGS

from .cdp import (
    download_url_to_file,
    export_netscape_cookies_via_cdp,
    fetch_douyin_detail_json_via_cdp,
)


_TRAILING_PUNCT = ")]}>,.;:!?'\"，。；：！？、】【）】》…"


class DouyinDownloaderError(RuntimeError):
    pass


@dataclass
class DownloadOptions:
    text: str
    output: str = "downloads"
    filename: str = "%(title).200B [%(id)s].%(ext)s"
    cookies: str | None = None
    cookies_from_browser: str | None = None
    cookies_from_cdp: str | None = None
    via_cdp: str | None = None
    cdp_port: int = 9222
    cdp_profile: str = "Default"
    cdp_user_data_dir: str | None = None
    cdp_headless: bool = False
    proxy: str | None = None
    no_watermark: bool = False
    info_json: bool = False
    audio_only: bool = False


def extract_url(text: str) -> str | None:
    m = re.search(r"https?://\S+", text)
    if not m:
        return None
    return m.group(0).strip().rstrip(_TRAILING_PUNCT)


def parse_cookies_from_browser(spec: str) -> tuple[str, str | None, str | None, str | None]:
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
        raise DouyinDownloaderError(f"invalid --cookies-from-browser value: {spec!r}")

    name, keyring, profile, container = m.group("name", "keyring", "profile", "container")
    name = name.lower().strip()
    if name not in SUPPORTED_BROWSERS:
        raise DouyinDownloaderError(
            f"unsupported browser for --cookies-from-browser: {name!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_BROWSERS))}"
        )

    if keyring is not None:
        keyring = keyring.upper().strip()
        if keyring not in SUPPORTED_KEYRINGS:
            raise DouyinDownloaderError(
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


def _safe_name(name: str) -> str:
    # 1) Remove Windows-illegal chars.
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    # 2) Remove ASCII control chars (including \n, \r, \t, NUL, etc.).
    name = re.sub(r"[\x00-\x1f\x7f]+", " ", name)
    # 3) Collapse whitespace/newlines into single spaces for stable filenames.
    name = re.sub(r"\s+", " ", name).strip()
    # 4) Windows disallows trailing space/dot in path components.
    name = name.rstrip(" .")
    # 5) Keep filename short enough for common Windows path limits.
    return (name[:120].strip() or "douyin").rstrip(" .")


def _fmt_size(n: float | int | None) -> str:
    if n is None:
        return "?"
    x = float(n)
    for unit in ["B", "KB", "MB", "GB"]:
        if x < 1024 or unit == "GB":
            return f"{x:.1f}{unit}" if unit != "B" else f"{int(x)}B"
        x /= 1024
    return f"{x:.1f}GB"


def download(opts: DownloadOptions, progress_cb: Callable[[str], None] | None = None) -> Path | None:
    raw_text = opts.text.strip()
    if not raw_text:
        raise DouyinDownloaderError("empty input text/url")
    url = extract_url(raw_text) or raw_text

    out_dir = Path(opts.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if opts.via_cdp:
        try:
            data = fetch_douyin_detail_json_via_cdp(
                browser=opts.via_cdp,
                url=url,
                port=opts.cdp_port,
                user_data_dir=opts.cdp_user_data_dir,
                profile=opts.cdp_profile,
                headless=bool(opts.cdp_headless),
                timeout_s=90.0,
            )
        except Exception as e:
            msg = str(e)
            if "failed to start" in msg.lower() and "cdp" in msg.lower():
                raise DouyinDownloaderError(
                    "CDP ????????? Edge/Chrome ????\n"
                    "?????????????Edge/Chrome?????????\n\n"
                    f"????: {msg}"
                )
            raise DouyinDownloaderError(msg)

        aweme = (data.get("aweme_detail") or data.get("awemeDetail") or {})
        desc = (aweme.get("desc") or "douyin").strip()
        aweme_id = str(aweme.get("aweme_id") or aweme.get("awemeId") or "video")
        video = aweme.get("video") or {}

        play = (video.get("play_addr") or video.get("playAddr") or {})
        url_list = play.get("url_list") or play.get("urlList") or []
        if not url_list:
            br = video.get("bit_rate") or video.get("bitRate") or []
            if br and isinstance(br, list):
                pa = (br[0].get("play_addr") or br[0].get("playAddr") or {})
                url_list = pa.get("url_list") or pa.get("urlList") or []

        if not url_list:
            raise DouyinDownloaderError("could not find playable URL in captured JSON (possible anti-bot/captcha)")

        media_url = url_list[0]
        out_path = out_dir / f"{_safe_name(desc)} [{aweme_id}].mp4"
        last_pct = {"v": -1}

        def _cdp_progress(done: int, total: int | None) -> None:
            if progress_cb is None:
                return
            if total and total > 0:
                pct = int(done * 100 / total)
                if pct == last_pct["v"]:
                    return
                last_pct["v"] = pct
                progress_cb(f"下载中 {pct}% ({_fmt_size(done)}/{_fmt_size(total)})")
            else:
                # Unknown total size.
                if done // (1024 * 1024) != last_pct["v"]:
                    last_pct["v"] = done // (1024 * 1024)
                    progress_cb(f"下载中 {_fmt_size(done)}")

        download_url_to_file(
            media_url,
            out_path,
            user_agent=None,
            referer="https://www.douyin.com/",
            progress_cb=_cdp_progress,
        )
        return out_path

    ydl_opts: dict = {
        "outtmpl": str(out_dir / opts.filename),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if opts.cookies_from_cdp and (opts.cookies or opts.cookies_from_browser or opts.via_cdp):
        raise DouyinDownloaderError("use only one of --cookies / --cookies-from-browser / --cookies-from-cdp")

    if opts.cookies:
        ydl_opts["cookiefile"] = opts.cookies
    if opts.cookies_from_browser:
        if opts.cookies:
            raise DouyinDownloaderError("use either --cookies or --cookies-from-browser (not both)")
        ydl_opts["cookiesfrombrowser"] = parse_cookies_from_browser(opts.cookies_from_browser)
    if opts.cookies_from_cdp:
        tmp_dir = Path(tempfile.mkdtemp(prefix="douyin-dl-"))
        tmp_cookies = tmp_dir / "cookies.txt"
        export_netscape_cookies_via_cdp(
            browser=opts.cookies_from_cdp,
            url=url,
            out_path=tmp_cookies,
            port=opts.cdp_port,
            user_data_dir=opts.cdp_user_data_dir,
            profile=opts.cdp_profile,
            headless=bool(opts.cdp_headless),
        )
        ydl_opts["cookiefile"] = str(tmp_cookies)

    if opts.proxy:
        ydl_opts["proxy"] = opts.proxy
    if opts.info_json:
        ydl_opts["writeinfojson"] = True

    if opts.audio_only:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ]
    else:
        ydl_opts["format"] = "bv*+ba/b" if opts.no_watermark else "bestvideo*+bestaudio/best"

    if progress_cb is not None:
        last = {"pct": -1}

        def _hook(d: dict) -> None:
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes") or 0
                if total:
                    pct = int(done * 100 / total)
                    if pct != last["pct"]:
                        last["pct"] = pct
                        speed = d.get("speed")
                        speed_text = f"{_fmt_size(speed)}/s" if speed else "?"
                        progress_cb(f"下载中 {pct}% ({_fmt_size(done)}/{_fmt_size(total)}), 速度 {speed_text}")
                else:
                    progress_cb(f"下载中 {_fmt_size(done)}")
            elif status == "finished":
                progress_cb("下载完成，正在合并/后处理...")

        ydl_opts["progress_hooks"] = [_hook]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        msg = str(e)
        if "Could not copy Chrome cookie database" in msg:
            raise DouyinDownloaderError(
                f"{msg}\n\n"
                "Hint:\n"
                "- Fully close browser, then retry\n"
                "- Or use --cookies cookies.txt\n"
            )
        if "Failed to decrypt with DPAPI" in msg:
            raise DouyinDownloaderError(
                f"{msg}\n\n"
                "Hint:\n"
                "- Try --cookies-from-cdp edge\n"
                "- Or use --cookies cookies.txt\n"
            )
        if "Fresh cookies" in msg or "cookies" in msg.lower():
            raise DouyinDownloaderError(
                f"{msg}\n\n"
                "Hint:\n"
                "- Use --cookies cookies.txt\n"
                "- Or --cookies-from-browser edge\n"
                "- Or --via-cdp edge (recommended)\n"
            )
        raise DouyinDownloaderError(msg)

    return None

