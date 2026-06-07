# 抖音视频下载器 - Mac 系统可用版

## 首次安装

1. 安装 Google Chrome。
2. 安装 Python 3。
3. 安装 ffmpeg：

```bash
brew install ffmpeg
```

4. 打开终端，进入本文件夹，然后运行：

```bash
chmod +x install_mac.sh douyin-download
./install_mac.sh
```

## 下载视频

运行：

```bash
./douyin-download
```

按提示粘贴抖音链接或完整分享文本，然后按回车。

下载好的视频会保存到：

```bash
downloads
```

## 如果某个视频失败

如果看到 `Fresh cookies` 或 `possible anti-bot/captcha`，先在 Chrome 里打开链接并确认视频可以播放，然后再运行 `./douyin-download`。
