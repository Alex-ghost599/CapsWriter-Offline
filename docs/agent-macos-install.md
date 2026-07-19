# CapsWriter-Offline-macOS Agent 安装执行规约

本文供运行在目标 Mac 上、具备终端访问能力的 AI agent 阅读。目标是协助人类完成
CapsWriter-Offline-macOS 的源码安装、权限配置和真实语音输入验收，而不是只执行导入测试或
dry-run。

## 当前锁定版本

| 项目 | 固定值 |
| --- | --- |
| 仓库 | `Alex-ghost599/CapsWriter-Offline-macOS` |
| Release | `v2.6.0-macos.2` |
| Git commit | `040e6ffc22ab214367a8ce1e834195ac4f95639d` |
| 安装脚本 SHA-256 | `b8d6f8fc861ae64c46a10e0cd9b224a18fe39323a6d4ba29673995cdf2e57b77` |
| 支持平台 | Apple Silicon macOS（`arm64`） |
| 默认安装目录 | `~/CapsWriter-Offline-macOS` |
| 默认录音键 | 右 Shift（`shift_r`） |

Release 是源码安装实验版，不包含预编译 App 或模型。安装阶段需要联网；安装完成后，默认
Paraformer 识别链路在本机离线运行。

## 完成标准

只有以下项目全部满足，agent 才能报告“安装与配置完成”：

1. 实际 checkout 精确对应 `v2.6.0-macos.2` 和上表 commit。
2. Python 3.12 与冻结依赖由 `uv` 安装；未使用裸 `pip` 或 `python -m venv`。
3. 两个模型已经下载并通过固定 SHA-256 校验。
4. `dist/CapsWriter.app` 是 arm64，且 `codesign --verify --deep --strict` 通过。
5. 服务端实际监听 `127.0.0.1:6016`，客户端实际启动。
6. 人类已亲自在 macOS 中确认麦克风、辅助功能、输入监控权限。
7. 人类使用真实物理麦克风，按住右 Shift 说话并松开，文本实际写入前台输入框。

静态检查、mock、预录音频或 agent 自述不能替代第 6、7 项。
如果人类选择延后模型，只能报告“基础环境和 App 已安装，真实听写验收未完成”。

## Agent 行为边界

- 先完整阅读本文，再执行命令；每个阶段都要检查退出码和关键输出。
- 不得删除、覆盖、`reset` 或清理任何已有安装目录。目标路径已存在时，先让人类选择新路径。
- 安装 Homebrew、修改配置或改变系统默认输入设备前，必须先征得人类确认。
- 所有 Python 环境、依赖和 Python 命令必须经 `uv`；不得创建其他 venv。
- 安装器和校验清单只从本文指定的 fork Release 下载，并同时验证 Release 清单和本文固定的
  脚本哈希；模型只允许通过仓库内的固定下载器获取和校验上游官方资产。
- 本安装与验收任务不得把服务端绑定到 `0.0.0.0`。当前协议没有认证，必须显式使用
  `127.0.0.1:6016`；局域网访问应作为单独任务重新评估风险。
- 不得代替人类声称已授予 TCC 权限，也不得用合成或回环音频冒充真人麦克风验收。
- 录音、日志和转写结果默认保存在本机。测试句不得含姓名、账号、工作内容等敏感信息；未经
  人类明确同意，不要读取或回传包含录音、转写正文的文件或日志。
- 不要把录音、转写文本、日志、本机用户名、设备名或私人路径上传到仓库或第三方服务。

## 阶段 0：向人类确认

开始前只需确认三件事：

1. 安装目录。推荐 `~/CapsWriter-Offline-macOS`；若已存在，必须改用新的目录。
2. 是否现在下载约 530 MB 模型。推荐现在下载；延后会使真实听写验收暂时无法进行。
3. 如果 Homebrew 缺失，是否允许执行 Homebrew 官方安装程序。

建议至少预留 5 GB 可用磁盘空间，以容纳源码、下载缓存、模型、Python 环境和构建产物。

## 阶段 1：只读预检

执行并向人类概括结果：

```bash
sw_vers -productVersion
uname -s
uname -m
df -h "$HOME"
command -v git || true
command -v brew || true
```

必须看到 `Darwin` 和 `arm64`。如果 `git` 缺失，运行 `xcode-select --install` 并等待人类完成
系统安装界面。如果 Homebrew 缺失，先获得确认，再使用 [Homebrew 官网](https://brew.sh)
当前提供的官方安装命令；安装后在 Apple Silicon Mac 上通常需要执行：

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

不要在不受支持的 Intel Mac 上继续。

## 阶段 2：下载并验证 Release 资产

使用新的临时目录，避免混用旧下载：

```bash
RELEASE=v2.6.0-macos.2
BASE_URL="https://github.com/Alex-ghost599/CapsWriter-Offline-macOS/releases/download/$RELEASE"
ASSET_DIR="$(mktemp -d "${TMPDIR:-/tmp}/capswriter-installer.XXXXXX")"

curl -fL "$BASE_URL/install-macos.sh" -o "$ASSET_DIR/install-macos.sh"
curl -fL "$BASE_URL/SHA256SUMS" -o "$ASSET_DIR/SHA256SUMS"

cd "$ASSET_DIR"
shasum -a 256 -c SHA256SUMS
printf '%s  %s\n' \
  'b8d6f8fc861ae64c46a10e0cd9b224a18fe39323a6d4ba29673995cdf2e57b77' \
  'install-macos.sh' | shasum -a 256 -c -
```

两次检查都必须输出 `install-macos.sh: OK`。失败时停止，不执行脚本，也不要通过关闭校验继续。

## 阶段 3：安装源码、模型和 App

先设置人类确认过的全新目录，并确认它不存在：

```bash
INSTALL_DIR="$HOME/CapsWriter-Offline-macOS"
test ! -e "$INSTALL_DIR" && test ! -L "$INSTALL_DIR"
```

默认完整安装：

```bash
bash "$ASSET_DIR/install-macos.sh" --install-dir "$INSTALL_DIR"
```

安装器会依次：

1. 通过 Homebrew 准备 `uv`、`ffmpeg`。
2. clone 固定 tag。
3. 用 `uv` 安装 Python 3.12 和 `uv.lock` 冻结依赖。
4. 下载并校验 Paraformer 与标点模型。
5. 本地构建 `dist/CapsWriter.app` 并校验其 ad-hoc 签名结构。

只有在人类明确要求延后模型时，才可使用：

```bash
bash "$ASSET_DIR/install-macos.sh" --install-dir "$INSTALL_DIR" --skip-models
```

此时必须明确报告“安装尚不能进行真实听写验收”，并在之后执行：

```bash
cd "$INSTALL_DIR"
uv run python scripts/download_macos_models.py
```

### 中途失败后的续接

安装器拒绝任何已存在目标目录，因此失败后不要直接重跑，也不要删除该目录。先区分失败发生
在 clone 前还是 clone 后：

```bash
if [[ ! -e "$INSTALL_DIR" && ! -L "$INSTALL_DIR" ]]; then
  printf '目标目录尚未创建：修复前置错误后，可用同一份已校验脚本重新安装。\n'
elif [[ -L "$INSTALL_DIR" ]]; then
  printf '目标路径是符号链接：保留现场并改用新的安装目录。\n'
elif [[ ! -d "$INSTALL_DIR/.git" ]]; then
  printf '目标路径存在但不是完整 checkout：保留现场并改用新的安装目录。\n'
else
  git -C "$INSTALL_DIR" status --short
  git -C "$INSTALL_DIR" rev-parse HEAD
  git -C "$INSTALL_DIR" describe --tags --exact-match HEAD
fi
```

目标目录尚未创建时，修复 Homebrew、Git、网络或其他前置错误后，使用原始命令重新运行同一份
已校验安装器。只有目录已经是完整 checkout，并且工作树干净、tag 和 commit 都与本文固定值
一致时，才可从实际失败步骤继续。下面列出各步骤的续接命令，不要无条件重跑已经成功的步骤：

```bash
cd "$INSTALL_DIR"
brew install uv ffmpeg
uv python install 3.12
uv sync --all-groups --frozen
uv run pyinstaller --noconfirm --clean packaging/macos/CapsWriterClient.spec
codesign --verify --deep --strict dist/CapsWriter.app
```

如果人类没有选择延后模型，或现在决定补齐模型，再单独执行：

```bash
cd "$INSTALL_DIR"
uv run python scripts/download_macos_models.py
```

如果 checkout 不匹配或有本地改动，停止并请人类选择另一个新目录，不得自动修复、重置或删除。

## 阶段 4：静态验收

```bash
test "$(git -C "$INSTALL_DIR" rev-parse HEAD)" = \
  '040e6ffc22ab214367a8ce1e834195ac4f95639d'
test "$(git -C "$INSTALL_DIR" describe --tags --exact-match HEAD)" = \
  'v2.6.0-macos.2'

cd "$INSTALL_DIR"
uv lock --check
test -d dist/CapsWriter.app
file dist/CapsWriter.app/Contents/MacOS/CapsWriter
codesign --verify --deep --strict dist/CapsWriter.app
```

`file` 必须报告 `Mach-O 64-bit executable arm64`。如果模型应当已经安装，再运行模型下载器
复核文件；正确情况下会快速报告两个模型已安装：

```bash
cd "$INSTALL_DIR"
uv run python scripts/download_macos_models.py
```

## 阶段 5：启动与权限配置

安装器不会自动启动程序。让服务端在一个持续运行的终端会话中保持前台运行：

```bash
cd "$INSTALL_DIR"
CAPSWRITER_SERVER_BIND=127.0.0.1 CAPSWRITER_SERVER_PORT=6016 \
  CAPSWRITER_MODEL_TYPE=paraformer uv run python start_server.py
```

在另一个终端确认本地监听：

```bash
lsof -nP -a -iTCP@127.0.0.1:6016 -sTCP:LISTEN
```

输出必须对应刚才启动的 CapsWriter 服务进程；其他程序占用同一端口或显示 `*:6016` 都不算通过。

然后启动客户端：

```bash
open "$INSTALL_DIR/dist/CapsWriter.app"
sleep 2
pgrep -fl 'CapsWriter.app/Contents/MacOS/CapsWriter'
```

`pgrep` 必须返回最终 App 内的客户端进程。

首次启动后，请人类前往“系统设置 > 隐私与安全性”，为最终的 `CapsWriter.app` 开启：

1. 麦克风
2. 辅助功能
3. 输入监控

这些开关必须由人类确认。修改后退出并重新打开 App；如果二进制后来重建，macOS 可能要求
重新授权。

## 阶段 6：配置与真人验收

- 日常使用保持 macOS 系统默认输入设备。切换“系统设置 > 声音 > 输入”后，重开 App。
- 默认按住右 Shift 录音，松开后上屏。没有额外键盘驱动时，不要改成 Caps Lock 长按。
- 如人类只想在源码调试模式临时测试其他单键，可执行：

```bash
cd "$INSTALL_DIR"
CAPSWRITER_HOTKEY=f10 uv run python start_client.py
```

源码模式的 TCC 授权对象与独立 App 不同，不能把它当成日常 App 已授权的证据。

真实验收步骤：

1. 打开 TextEdit，新建空白文档并把光标放入编辑区。
2. 由人类按住右 Shift 至少 0.3 秒，用真实物理麦克风说一句不含私人信息的临时测试语句，
   然后松开。
3. 确认识别文本实际写入 TextEdit，而不是只出现在日志或剪贴板。
4. 若未上屏，先检查系统默认输入、三项 TCC 权限、端口监听以及日志中的状态和错误行。未经
   人类明确同意，不要打开或回传包含录音、转写正文的文件或日志。

不要在报告中记录人类说出的原文，只记录“真人物理麦克风上屏：通过/未通过”。

## 阶段 7：退出与最终报告

完成测试后退出 CapsWriter 客户端，并在服务端终端按 `Ctrl-C`。确认端口已经释放：

```bash
lsof -nP -a -iTCP@127.0.0.1:6016 -sTCP:LISTEN
```

最终向人类报告：

- macOS 版本与 `arm64` 结果
- 安装目录
- Release、tag、commit 和脚本 SHA-256
- Python/依赖安装是否成功
- 模型是已校验安装还是经人类同意延后
- App arm64 与 `codesign` 结果
- 三项 TCC 权限是否由人类确认
- 真人物理麦克风上屏是否由人类确认
- 尚未完成的步骤、具体错误和下一条安全操作

任何一项未完成，都应如实标记，不得用“基本可用”或“smoke 通过”替代。
