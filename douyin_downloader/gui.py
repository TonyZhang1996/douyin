from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from .downloader import DownloadOptions, DouyinDownloaderError, download
except ImportError:
    # PyInstaller may execute this module without package context.
    from douyin_downloader.downloader import DownloadOptions, DouyinDownloaderError, download


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("抖音视频下载器")
        self.geometry("760x560")
        self.minsize(700, 520)
        self.configure(bg="#f3f6fb")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#f3f6fb")
        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 15, "bold"), background="#f3f6fb")
        style.configure("TLabel", font=("Microsoft YaHei UI", 10), background="#f3f6fb")
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"))

        self.input_text = tk.StringVar()
        self.output_dir = tk.StringVar(value=str((Path.cwd() / "downloads").resolve()))
        self.browser = tk.StringVar(value="edge")
        self.mode = tk.StringVar(value="CDP 高成功率（推荐）")
        self.is_running = False

        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="抖音视频下载器（EXE 版）", style="Header.TLabel").pack(anchor="w")
        ttk.Label(root, text="粘贴抖音分享文案或链接，点击下载即可。").pack(anchor="w", pady=(2, 14))

        input_box = ttk.Frame(root)
        input_box.pack(fill="x")
        ttk.Label(input_box, text="分享内容 / 链接").pack(anchor="w")
        self.text_widget = tk.Text(
            input_box,
            height=8,
            font=("Microsoft YaHei UI", 10),
            relief="solid",
            borderwidth=1,
            wrap="word",
        )
        self.text_widget.pack(fill="x", pady=(6, 10))

        line1 = ttk.Frame(root)
        line1.pack(fill="x", pady=4)
        ttk.Label(line1, text="下载目录").pack(side="left")
        ttk.Entry(line1, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(line1, text="选择目录", command=self.pick_dir).pack(side="left")

        line2 = ttk.Frame(root)
        line2.pack(fill="x", pady=4)
        ttk.Label(line2, text="下载模式").pack(side="left")
        ttk.Combobox(
            line2,
            textvariable=self.mode,
            values=["CDP 高成功率（推荐）", "标准 yt-dlp（兼容）"],
            state="readonly",
            width=24,
        ).pack(side="left", padx=8)
        ttk.Label(line2, text="浏览器").pack(side="left")
        ttk.Combobox(
            line2,
            textvariable=self.browser,
            values=["edge", "chrome"],
            state="readonly",
            width=10,
        ).pack(side="left", padx=8)

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(10, 8))
        self.download_btn = ttk.Button(btns, text="开始下载", style="Primary.TButton", command=self.start_download)
        self.download_btn.pack(side="left")
        ttk.Button(btns, text="打开下载目录", command=self.open_dir).pack(side="left", padx=8)
        ttk.Button(btns, text="清空日志", command=self.clear_log).pack(side="left")

        ttk.Label(root, text="运行日志").pack(anchor="w", pady=(10, 4))
        self.log_widget = tk.Text(
            root,
            height=12,
            font=("Consolas", 10),
            bg="#111827",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            relief="solid",
            borderwidth=1,
        )
        self.log_widget.pack(fill="both", expand=True)
        self._log("就绪：请粘贴抖音链接并点击“开始下载”。")

    def _log(self, text: str) -> None:
        self.log_widget.insert("end", text + "\n")
        self.log_widget.see("end")
        self.update_idletasks()

    def clear_log(self) -> None:
        self.log_widget.delete("1.0", "end")

    def pick_dir(self) -> None:
        picked = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.cwd()))
        if picked:
            self.output_dir.set(picked)

    def open_dir(self) -> None:
        out = Path(self.output_dir.get().strip() or "downloads")
        out.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out))

    def start_download(self) -> None:
        if self.is_running:
            return
        text = self.text_widget.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "请先粘贴抖音分享文案或链接。")
            return
        out = self.output_dir.get().strip()
        if not out:
            messagebox.showwarning("提示", "请先选择下载目录。")
            return

        self.is_running = True
        self.download_btn.config(state="disabled")
        t = threading.Thread(target=self._run_download, daemon=True)
        t.start()

    def _run_download(self) -> None:
        try:
            text = self.text_widget.get("1.0", "end").strip()
            self._log("开始下载...")
            mode = self.mode.get().strip()
            browser = self.browser.get().strip()
            opts = DownloadOptions(
                text=text,
                output=self.output_dir.get().strip(),
                via_cdp=browser if mode.startswith("CDP") else None,
                cookies_from_browser=None if mode.startswith("CDP") else browser,
                cdp_headless=True if mode.startswith("CDP") else False,
            )
            out = download(opts)
            if out is not None:
                self._log(f"下载完成: {out}")
            else:
                self._log("下载完成。")
            messagebox.showinfo("完成", "下载完成。")
        except DouyinDownloaderError as e:
            self._log(f"ERROR: {e}")
            messagebox.showerror("下载失败", str(e))
        except Exception as e:
            self._log(f"ERROR: {e}")
            messagebox.showerror("下载失败", str(e))
        finally:
            self.is_running = False
            self.download_btn.config(state="normal")


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
