# 抖音视频下载器

一个开源的命令行工具：输入抖音分享文本或视频链接，即可下载视频。

底层默认使用 `yt-dlp`，并提供 `CDP` 模式来提升在风控场景下的成功率。

## 安装

### 方式 A：可编辑安装（推荐开发时使用）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
```

### 方式 B：普通安装

```powershell
pip install .
```

## 使用方法

### 1. 最基础用法

```powershell
douyin-dl "<抖音分享文本或视频链接>"
```

说明：支持直接粘贴整段分享文案，程序会自动提取其中第一个 `http(s)` 链接。

### 2. 指定下载目录

```powershell
douyin-dl "<url>" -o downloads
```

### 3. 使用 cookies.txt（常见于风控/需登录场景）

先从浏览器导出 `cookies.txt`（Netscape 格式），然后执行：

```powershell
douyin-dl "<url>" --cookies .\cookies.txt
```

### 4. 直接读取浏览器 cookies

```powershell
douyin-dl "<url>" --cookies-from-browser edge
```

### 5. 高成功率模式（推荐）：`--via-cdp`

当 `yt-dlp` 在 cookies 场景下仍被拦截时，使用 CDP 模式（通过真实浏览器会话抓取详情接口后下载）：

```powershell
douyin-dl "<url>" --via-cdp edge
```

## 常见问题

- 如果命令中包含 `#` 等字符，请用双引号包住整段文本（PowerShell 不加引号会把 `#` 后内容当注释）。
- 若视频和音频是分离流，`yt-dlp` 可能需要本机安装 `ffmpeg` 才能自动合并。
- 若出现验证码/滑块，需要在弹出的浏览器中手动完成验证后重试。

## 免责声明

- 本项目仅用于个人学习与研究。
- 请遵守你所在地区法律法规，以及抖音平台服务条款。

## 许可证

MIT，见 `LICENSE`。
