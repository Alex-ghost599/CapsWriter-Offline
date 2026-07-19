# macOS 安装与运行

当前适配目标为 Apple Silicon macOS。默认使用 Paraformer 语音模型和
Punct-CT-Transformer 标点模型，服务端与客户端均在本机离线运行。

## 推荐：从 Release 安装源码版

[`v2.6.0-macos.1`](https://github.com/Alex-ghost599/CapsWriter-Offline-macOS/releases/tag/v2.6.0-macos.1)
是 macOS 源码安装实验版。Release 不包含预编译 App 或模型，只提供可审查的安装脚本和
SHA-256 校验文件；脚本会拉取固定 tag、以 `uv` 安装冻结依赖、校验下载模型并在本机
构建 `CapsWriter.app`。

先安装 [Homebrew](https://brew.sh)，再在终端执行：

```bash
BASE_URL=https://github.com/Alex-ghost599/CapsWriter-Offline-macOS/releases/download/v2.6.0-macos.1
curl -fLO "$BASE_URL/install-macos.sh"
curl -fLO "$BASE_URL/SHA256SUMS"
shasum -a 256 -c SHA256SUMS
bash install-macos.sh
```

默认安装到 `~/CapsWriter-Offline-macOS`，并下载约 530 MB 的 Paraformer 和标点模型。
暂时不下载模型可执行：

```bash
bash install-macos.sh --skip-models
```

其他可用参数见 `bash install-macos.sh --help`。只要安装目录已经存在，安装器就会在执行
Homebrew 前停止；请改用新的 `--install-dir`，已有目录始终由用户手动管理。安装器不会
自动启动服务或客户端。每台 Mac 都需要各自执行安装，并分别授予麦克风、辅助功能和
输入监控权限。

## 1. 手动安装环境

```bash
brew install uv ffmpeg
git clone --depth 1 --branch v2.6.0-macos.1 \
  https://github.com/Alex-ghost599/CapsWriter-Offline-macOS.git \
  ~/CapsWriter-Offline-macOS
cd ~/CapsWriter-Offline-macOS
uv python install 3.12
uv sync --all-groups --frozen
```

仓库固定 Python 3.12，所有解释器、虚拟环境与 Python 依赖均由 `uv` 管理。
不要在项目内使用裸 `pip` 或 `python -m venv`。

## 2. 下载模型

```bash
uv run python scripts/download_macos_models.py
```

脚本从上游 GitHub Releases 下载两个官方 ZIP，逐个校验 SHA-256，拒绝越界路径和
符号链接，再安装到 Git 忽略的 `models/` 子目录。安装记录同时保存必需模型
文件哈希；重复执行会重新校验，如文件被损坏则从已校验 ZIP 自动修复。

## 3. 启动服务端

```bash
CAPSWRITER_MODEL_TYPE=paraformer uv run python start_server.py
```

服务默认仅监听 `127.0.0.1:6016`。保持此终端运行。WebSocket 对单帧、
连接数、分段参数、缓冲和单任务时长均有上限。如确需让局域网客户端连接，
可显式设置 `CAPSWRITER_SERVER_BIND=0.0.0.0`；当前协议没有身份验证，只能在
受信网络中这样做。远程客户端另用 `CAPSWRITER_SERVER_ADDR=<服务端 IP>`
指定连接目标；端口可在两端统一设置 `CAPSWRITER_SERVER_PORT`。

## 4. 构建客户端应用

```bash
uv run pyinstaller --noconfirm --clean packaging/macos/CapsWriterClient.spec
open dist/CapsWriter.app
```

客户端应用使用独立 Bundle ID
`io.github.alex-ghost599.capswriter-offline.client`。日志、热词、录音和日记位于
`~/Library/Application Support/CapsWriter-Offline`，不会写入 `.app` 内部。

首次启动后，在“系统设置 > 隐私与安全性”中为 `CapsWriter` 开启：

1. 麦克风
2. 辅助功能
3. 输入监控

修改权限后退出并重新打开 `CapsWriter.app`。这些权限分别用于采集语音、发送
Command-V 和监听全局右 Shift。按住右 Shift 说话，松开后识别文本会写入当前前台输入框；
写入过程会保留并恢复剪贴板的原始多类型内容。

手动构建使用 ad-hoc 签名。每次重建二进制后，macOS 可能不继承上一版的
TCC 授权，需删除旧权限项、重新添加最终 `CapsWriter.app` 并再启动。要做稳定
的免警告二进制分发，仍需 Apple Developer 签名身份与公证；这不影响当前源码安装版
作为 GitHub Release 发布和使用。

## 5. 源码调试

源码模式可直接运行：

```bash
uv run python start_client.py
```

macOS 会把 TCC 权限关联到启动进程链。日常使用建议授权独立的 `CapsWriter.app`，
不要长期给通用 Python 解释器开放辅助功能和输入监控。

可用以下环境变量选择输入设备或首选采样率：

```bash
CAPSWRITER_AUDIO_DEVICE=7 CAPSWRITER_AUDIO_SAMPLE_RATE=48000 \
  uv run python start_client.py
```

macOS 默认仅配置右 Shift（`shift_r`）作为录音键。可编辑 `config_client.py` 后重启，或在源码/终端
启动 app 时用 `CAPSWRITER_HOTKEY=f10` 临时选择其他单键。当前仅支持普通单键，不支持
`Option+Space` 这类修饰键组合。

Finder 启动的应用会自动检查 Homebrew 的 `/opt/homebrew/bin` 和 `/usr/local/bin`。
如使用自定义 FFmpeg，可设置 `CAPSWRITER_FFMPEG` 与 `CAPSWRITER_FFPROBE` 为完整路径。

设备不支持首选采样率时，客户端会自动退回设备默认采样率，并高质量重采样到服务端
要求的 16 kHz 单声道浮点音频。

macOS 适配默认关闭可选 LLM 角色润色，专注于完全离线 ASR 主链路。如要开启，
需先在 `config_client.py` 设置 `llm_enabled = True`，并为应用数据目录准备角色配置。

## 6. 验证

```bash
uv lock --check
uv run pytest -q
bash scripts/lint_macos_port.sh
```

文件识别可使用模型自带的真实语音：

```bash
uv run python start_client.py \
  models/Paraformer/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx/example/asr_example.wav
```

模型目录、录音、日志、构建目录与识别副产物均由 `.gitignore` 排除，不提交到 fork。
