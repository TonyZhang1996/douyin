from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


def _run_quiet(cmd: list[str], timeout: int = 5) -> None:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
        startupinfo=si,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _http_json(url: str, timeout: float = 2.0):
    req = urllib.request.Request(url, headers={"User-Agent": "douyin-dl"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8", errors="replace"))


def _try_http_json(url: str, timeout: float = 1.0):
    try:
        return _http_json(url, timeout=timeout)
    except Exception:
        return None


def _find_browser_exe(browser: str) -> Path:
    candidates: list[str] = []
    if browser == "edge":
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
    elif browser == "chrome":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    else:
        raise ValueError(f"unsupported browser: {browser!r}")

    for p in candidates:
        pp = Path(p)
        if pp.exists():
            return pp
    raise FileNotFoundError(f"could not find {browser} executable in default locations")


def _default_user_data_dir(browser: str) -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    if browser == "edge":
        return Path(local) / "Microsoft" / "Edge" / "User Data"
    if browser == "chrome":
        return Path(local) / "Google" / "Chrome" / "User Data"
    raise ValueError(f"unsupported browser: {browser!r}")


def _wait_port(port: int, timeout_s: float = 10.0) -> bool:
    deadline = time.time() + timeout_s
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        if _try_http_json(url, timeout=0.5):
            return True
        time.sleep(0.2)
    return False


@dataclass
class CdpSession:
    browser: str
    port: int
    proc: subprocess.Popen | None
    temp_user_data_dir: Path | None = None


def _candidate_ports(preferred_port: int) -> list[int]:
    # Keep retries short to avoid repeatedly spawning many browser windows.
    ports = [preferred_port]
    for p in range(9223, 9226):
        if p != preferred_port:
            ports.append(p)
    return ports


def _start_browser_once(
    *,
    browser: str,
    port: int,
    user_data_dir: Path,
    profile: str,
    headless: bool,
) -> subprocess.Popen:
    exe = _find_browser_exe(browser)
    args = [
        str(exe),
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={str(user_data_dir)}",
        f"--profile-directory={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    if headless:
        args.insert(1, "--headless=new")
        args.insert(1, "--disable-gpu")

    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def start_cdp_browser(
    browser: str,
    port: int = 9222,
    user_data_dir: str | None = None,
    profile: str = "Default",
    headless: bool = False,
) -> CdpSession:
    if _try_http_json(f"http://127.0.0.1:{port}/json/version", timeout=0.5):
        return CdpSession(browser=browser, port=port, proc=None)

    base_udd = Path(user_data_dir) if user_data_dir else _default_user_data_dir(browser)
    ports = _candidate_ports(port)
    last_error: str | None = None

    for i, p in enumerate(ports):
        if _try_http_json(f"http://127.0.0.1:{p}/json/version", timeout=0.5):
            return CdpSession(browser=browser, port=p, proc=None)
        # Only the first attempt uses the requested headless mode.
        # Retries run headless to avoid many visible blank windows.
        attempt_headless = headless or i > 0
        proc = _start_browser_once(
            browser=browser,
            port=p,
            user_data_dir=base_udd,
            profile=profile,
            headless=attempt_headless,
        )
        if _wait_port(p, timeout_s=12.0):
            return CdpSession(browser=browser, port=p, proc=proc)
        try:
            _run_quiet(["taskkill", "/PID", str(proc.pid), "/T", "/F"])
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        last_error = f"failed on port {p}"

    if user_data_dir is None:
        temp_udd = Path(tempfile.mkdtemp(prefix=f"{browser}-cdp-"))
        for p in ports:
            if _try_http_json(f"http://127.0.0.1:{p}/json/version", timeout=0.5):
                return CdpSession(browser=browser, port=p, proc=None, temp_user_data_dir=temp_udd)
            proc = _start_browser_once(
                browser=browser,
                port=p,
                user_data_dir=temp_udd,
                profile=profile,
                headless=True,
            )
            if _wait_port(p, timeout_s=12.0):
                return CdpSession(browser=browser, port=p, proc=proc, temp_user_data_dir=temp_udd)
            try:
                _run_quiet(["taskkill", "/PID", str(proc.pid), "/T", "/F"])
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            last_error = f"failed with temp profile on port {p}"
        shutil.rmtree(temp_udd, ignore_errors=True)

    raise RuntimeError(
        f"failed to start {browser} with CDP. tried ports: {', '.join(map(str, ports))}. "
        f"last_error: {last_error or 'unknown'}. "
        "Try closing Edge/Chrome and retry."
    )


def stop_cdp_browser(session: CdpSession) -> None:
    try:
        if session.proc:
            try:
                _run_quiet(["taskkill", "/PID", str(session.proc.pid), "/T", "/F"])
            except Exception:
                try:
                    session.proc.terminate()
                except Exception:
                    pass
    finally:
        if session.temp_user_data_dir is not None:
            shutil.rmtree(session.temp_user_data_dir, ignore_errors=True)


def export_netscape_cookies_via_cdp(
    *,
    browser: str,
    url: str,
    out_path: Path,
    port: int = 9222,
    user_data_dir: str | None = None,
    profile: str = "Default",
    headless: bool = False,
) -> None:
    # Import here so base install stays light unless used.
    from websocket import create_connection  # type: ignore

    session = start_cdp_browser(
        browser=browser,
        port=port,
        user_data_dir=user_data_dir,
        profile=profile,
        headless=headless,
    )
    try:
        # New target endpoint may be disabled (405) on some Edge builds. Reuse an existing page target.
        cdp_port = session.port
        targets = _http_json(f"http://127.0.0.1:{cdp_port}/json/list", timeout=2.0)
        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise RuntimeError("CDP did not expose any page targets on /json/list")
        page = next((t for t in pages if (t.get("url") or "").startswith("about:blank")), pages[0])
        ws_url = page["webSocketDebuggerUrl"]

        ws = create_connection(ws_url, timeout=10)
        try:
            msg_id = 0

            def send(method: str, params: dict | None = None) -> int:
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method}
                if params:
                    payload["params"] = params
                ws.send(json.dumps(payload))
                return msg_id

            def recv_until(target_id: int, timeout_s: float = 20.0) -> dict:
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    raw = ws.recv()
                    obj = json.loads(raw)
                    if obj.get("id") == target_id:
                        return obj
                raise TimeoutError(f"timeout waiting for response id={target_id}")

            def wait_event(method: str, timeout_s: float = 30.0) -> None:
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    raw = ws.recv()
                    obj = json.loads(raw)
                    if obj.get("method") == method:
                        return
                raise TimeoutError(f"timeout waiting for event {method}")

            send("Page.enable")
            send("Network.enable")

            nav_id = send("Page.navigate", {"url": url})
            recv_until(nav_id, timeout_s=20.0)
            # Wait for the page to load; cookies may be updated during navigation.
            try:
                wait_event("Page.loadEventFired", timeout_s=30.0)
            except TimeoutError:
                # Some pages may keep loading; still try to export cookies.
                pass
            time.sleep(1.0)

            ck_id = send("Network.getAllCookies")
            ck = recv_until(ck_id, timeout_s=20.0)
            cookies = ck.get("result", {}).get("cookies", [])

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8", newline="\n") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Exported via CDP (DevTools Protocol)\n\n")
                for c in cookies:
                    domain = c.get("domain", "")
                    name = c.get("name", "")
                    value = c.get("value", "")
                    path = c.get("path", "/")
                    secure = "TRUE" if c.get("secure") else "FALSE"
                    # CDP returns expires as seconds since epoch (float). Netscape expects int.
                    expires = c.get("expires")
                    if not expires:
                        expires_i = 0
                    else:
                        try:
                            expires_i = int(float(expires))
                        except Exception:
                            expires_i = 0
                    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                    # domain, include_subdomains, path, secure, expires, name, value
                    f.write(
                        "\t".join(
                            [
                                domain,
                                include_subdomains,
                                path,
                                secure,
                                str(expires_i),
                                name,
                                value,
                            ]
                        )
                        + "\n"
                    )
        finally:
            try:
                ws.close()
            except Exception:
                pass
    finally:
        stop_cdp_browser(session)


def fetch_douyin_detail_json_via_cdp(
    *,
    browser: str,
    url: str,
    port: int = 9222,
    user_data_dir: str | None = None,
    profile: str = "Default",
    headless: bool = False,
    timeout_s: float = 60.0,
) -> dict:
    """
    Navigate to the given Douyin URL in a real browser profile via CDP, then
    capture the aweme detail JSON response from Network events.
    """
    from websocket import create_connection  # type: ignore

    session = start_cdp_browser(
        browser=browser,
        port=port,
        user_data_dir=user_data_dir,
        profile=profile,
        headless=headless,
    )
    try:
        cdp_port = session.port
        targets = _http_json(f"http://127.0.0.1:{cdp_port}/json/list", timeout=2.0)
        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise RuntimeError("CDP did not expose any page targets on /json/list")
        page = next((t for t in pages if (t.get("url") or "").startswith("about:blank")), pages[0])
        ws_url = page["webSocketDebuggerUrl"]

        ws = create_connection(ws_url, timeout=10)
        try:
            msg_id = 0
            candidates: dict[str, str] = {}  # requestId -> response URL

            def send(method: str, params: dict | None = None) -> int:
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method}
                if params:
                    payload["params"] = params
                ws.send(json.dumps(payload))
                return msg_id

            def recv_obj(deadline: float):
                timeout = max(0.1, min(1.0, deadline - time.time()))
                ws.settimeout(timeout)
                raw = ws.recv()
                return json.loads(raw)

            send("Page.enable")
            send("Network.enable")

            # Navigate and then watch network for the detail JSON call.
            send("Page.navigate", {"url": url})

            deadline = time.time() + timeout_s
            while time.time() < deadline:
                try:
                    obj = recv_obj(deadline)
                except Exception:
                    continue

                method = obj.get("method")
                params = obj.get("params") or {}

                if method == "Network.responseReceived":
                    resp = params.get("response") or {}
                    req_id = params.get("requestId")
                    resp_url = resp.get("url", "")
                    mime = (resp.get("mimeType") or "").lower()
                    if not req_id:
                        continue

                    # Only accept the exact aweme detail endpoint.
                    try:
                        path = urllib.parse.urlparse(resp_url).path
                    except Exception:
                        path = ""
                    is_detail = path.startswith("/aweme/v1/web/aweme/detail/")
                    if is_detail and ("json" in mime or "application/json" in mime or "text/plain" in mime):
                        candidates[req_id] = resp_url

                if method == "Network.loadingFinished":
                    req_id = params.get("requestId")
                    if req_id in candidates:
                        body_id = send("Network.getResponseBody", {"requestId": req_id})
                        # Wait for the response for this id.
                        while time.time() < deadline:
                            try:
                                o2 = recv_obj(deadline)
                            except Exception:
                                continue
                            if o2.get("id") != body_id:
                                continue
                            result = o2.get("result") or {}
                            body = result.get("body", "")
                            if result.get("base64Encoded"):
                                import base64

                                body = base64.b64decode(body).decode("utf-8", errors="replace")
                            try:
                                obj = json.loads(body)
                                # Attach debugging metadata for callers.
                                if isinstance(obj, dict):
                                    obj.setdefault("__cdp_captured_url", candidates.get(req_id))
                                return obj
                            except Exception:
                                # Keep searching; sometimes the response isn't JSON (blocked)
                                break

            raise TimeoutError("timed out waiting for /aweme/v1/web/aweme/detail/ JSON via CDP")
        finally:
            try:
                ws.close()
            except Exception:
                pass
    finally:
        stop_cdp_browser(session)


def download_url_to_file(url: str, out_path: Path, *, user_agent: str | None = None, referer: str | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent or "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        with out_path.open("wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
