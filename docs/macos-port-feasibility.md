# CapsWriter-Offline macOS 适配可行性审计

审计日期：2026-07-19

审计基线：`7d7fac3541a998be10ebf15102f7884a7dd36edb`（上游 `master`）

目标环境：Apple Silicon、macOS arm64

## 结论

macOS 适配**可行**，但不是修改依赖列表后即可运行的小改动。服务端的识别算法、WebSocket 通信和大部分音频处理基本跨平台；主要工作集中在客户端全局快捷键、按键拦截、文本注入、权限、菜单栏生命周期和应用打包。

建议先交付“独立 WAV/WebSocket 测试工具 + 命令行服务端 + 粘贴式客户端 + 单个 F 功能键”的最小版本，再实现 Caps Lock 拦截、Qwen/FunASR Metal 加速和签名后的菜单栏应用。现阶段不建议直接追求与 Windows 版完全等价。

建议优先路线如下：

1. 用独立测试工具向服务端发送固定 WAV，先以 Paraformer CPU 跑通识别，不经过现有客户端入口。
2. 拆开客户端的快捷键/UI 提前导入，再以单个 F 功能键和粘贴输出跑通客户端。
3. 增加 macOS 快捷键后端、权限预检和 Caps Lock 抑制/恢复。
4. 接入 llama.cpp `b7798` arm64 动态库，实测 Qwen/FunASR 的 Metal 性能。
5. 最后处理菜单栏、`.app`、签名、公证和升级分发。

## 审计范围与证据

本次只进行静态审计和无模型的运行前验证，没有修改现有业务代码，也没有下载语音模型。

已完成的验证：

- `python -m compileall`：项目 Python 源码编译通过，共生成 337 个临时字节码文件，缓存写入临时目录。
- 客户端依赖 `pip --dry-run`：在 macOS arm64 / Python 3.13 上可解析。
- 服务端依赖 `pip --dry-run`：因 `onnxruntime-directml` 无 macOS 发行包而失败，符合预期。
- `sherpa-onnx`：本次可解析到 `sherpa-onnx==1.13.4` 的 macOS 11+ arm64 / Python 3.13 wheel。
- llama.cpp `b7798`：官方发布中存在 `llama-b7798-bin-macos-arm64.tar.gz`；SHA-256 为 `b47219a34e0c966813e9a3083432cb37fc219c2b06c13dd893e2b13ae8eeb122`，确认包含 arm64 的 `libggml.dylib`、`libggml-base.dylib`、`libllama.dylib`、Metal/CPU/BLAS 等配套库。
- 使用 `DYLD_LIBRARY_PATH` 指向完整发布目录后，三个项目当前显式加载的动态库均可通过 `ctypes.CDLL` 加载；关键 llama API 符号存在。
- 当前仓库不包含完整模型和这些动态库，因此尚未验证真实识别延迟、内存峰值和准确率。

关键验证可按以下方式重放；依赖解析结果会随 PyPI 更新而变化，不能替代后续 lockfile：

```bash
tmp="$(mktemp -d)"
PYTHONPYCACHEPREFIX="$tmp/pycache" python3 -m compileall -q .
python3 -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install --dry-run -r requirements-client.txt
"$tmp/venv/bin/python" -m pip install --dry-run -r requirements-server.txt

gh release download b7798 --repo ggml-org/llama.cpp \
  --pattern llama-b7798-bin-macos-arm64.tar.gz --dir "$tmp"
echo "b47219a34e0c966813e9a3083432cb37fc219c2b06c13dd893e2b13ae8eeb122  $tmp/llama-b7798-bin-macos-arm64.tar.gz" \
  | shasum -a 256 -c -
tar -xzf "$tmp/llama-b7798-bin-macos-arm64.tar.gz" -C "$tmp"
file "$tmp"/build/bin/*.dylib
otool -L "$tmp"/build/bin/libllama.dylib
```

## 兼容性矩阵

| 模块 | 当前 macOS 状态 | 判断 |
| --- | --- | --- |
| WebSocket C/S 通信 | 无明显平台绑定 | 可直接复用 |
| 麦克风采集 | `sounddevice` 跨平台 | 基本可复用，需权限和采样率兜底 |
| 音频文件转录 | 现有入口提前导入 Win32 快捷键和 Tk | 需独立测试工具或先拆分客户端导入；之后还需 `ffmpeg` |
| Paraformer | `sherpa-onnx` 有 arm64 wheel | 最适合首个服务端 MVP |
| SenseVoice ONNX | 已有 CPU provider 路径，但服务端依赖闭包不完整 | 补齐依赖后进入运行验证，尚未确认可运行 |
| Qwen/FunASR GGUF | 已有 Darwin 动态库文件名分支 | 可适配，必须带完整 `b7798` 库集并实测模型 |
| 全局快捷键 | Win32 事件过滤器和虚拟键码 | 必须重写平台后端 |
| 文本输出 | 默认依赖 `keyboard.write` | macOS MVP 应强制粘贴模式 |
| 当前窗口检测 | macOS 分支能力很有限 | 需要按进程/Bundle ID 重做 |
| 托盘/菜单栏 | 代码显式禁用非 Windows | 需要重做主线程生命周期 |
| Toast/Tk UI | 当前解释器缺少 `_tkinter` | MVP 应关闭，后续改原生 UI 或固定运行时 |
| PyInstaller 打包 | spec 和资源路径偏 Windows | 需要单独 macOS spec、plist、签名和公证流程 |

## 关键阻塞点

### 1. 快捷键层硬编码 Win32

- `core/client/shortcut/key_mapper.py:9` 无条件导入 `pynput._util.win32.KeyTranslator`，macOS 启动时即会碰到内部 Win32 后端绑定。
- `core/client/shortcut/shortcut_manager.py:96-162` 的键盘和鼠标事件处理读取 `vkCode`、`mouseData` 和 Windows 消息常量。
- `core/client/shortcut/shortcut_manager.py:261-273` 只向 pynput listener 传入 `win32_event_filter`。
- 默认配置 `config_client.py:18-33` 同时启用了 Caps Lock 和鼠标侧键，并要求 `suppress=True`。

不能只把 `win32_event_filter` 政名。应先定义平台无关的按下、释放、抑制和恢复语义，然后保留 Windows 后端，新增 Darwin 后端。macOS 可先使用 pynput 的普通 listener 或 `darwin_intercept`，需要可靠拦截时再使用 Quartz `CGEventTap`。

首个 MVP 不应以 Caps Lock 为前置条件。现有任务表按单个键名索引，没有修饰键组合状态机，因此应先使用单个 F 功能键（例如 F8）验证录音和识别主链路。若采用 `Option+Space`，还必须实现组合键解析、抑制及释放顺序，不能把它视为零成本配置变更。

### 2. `keyboard` 库不能承担 macOS 核心输入

- `core/client/output/text_output.py:15,147` 无条件导入并调用 `keyboard.write`。
- `core/client/output/result_processor.py:48,150` 调用 `keyboard.press_and_release`，并读取私有字段 `_pressed_events`。
- `core/client/llm/llm_get_selection.py:45` 硬编码 `ctrl+c`。
- `core/client/llm/llm_output_typing.py:87-124` 的流式输出也依赖 `keyboard.write`。

`keyboard` 官方仓库将 Linux/Windows 作为主要支持平台，macOS 支持仍标为实验性，且按键抑制只支持 Windows。它不适合作为 macOS 的可靠输入后端。

项目已有可利用的基础：`core/client/output/text_output.py:119-126` 和 `core/client/clipboard/clipboard.py:125` 已选择 `Command+V`。macOS MVP 应把所有文本输出统一到“写剪贴板 + Command+V”，自动回车和复制选区则改由 pynput/Quartz 的平台后端发送。

当前粘贴实现只通过 `pyclip.paste().decode('utf-8')` 保存纯文本，并在固定 100 ms 后恢复。原剪贴板若包含图片、文件或富文本会丢失，较慢应用也可能尚未消费粘贴内容。macOS 版必须二选一：使用 `NSPasteboard` 完整保存/恢复所有 item 与 UTI，并依据 `changeCount` 避免覆盖用户的新剪贴板；或者默认不恢复并明确暴露此限制。不能直接沿用现状后宣称剪贴板安全。

### 3. macOS 权限不是可选项

至少需要处理：

- 麦克风权限：录音依赖；`.app` 的 `Info.plist` 需要 `NSMicrophoneUsageDescription`。
- 辅助功能权限：向其他应用发送粘贴、回车或其他合成事件时需要。
- 输入监控权限：全局监听或 Event Tap 的具体实现可能需要，尤其是按键抑制。

开发脚本、终端中的 Python 和签名后的 `.app` 会被 macOS 视为不同授权主体。产品化前必须固定 Bundle ID 和签名身份，并提供启动时预检与明确错误提示，否则开发环境可用不代表打包后可用。

### 4. 服务端依赖写死 DirectML

`requirements-server.txt:5` 无条件依赖 `onnxruntime-directml`，该包面向 Windows，macOS arm64 无匹配发行包。应使用平台标记拆分：

```text
onnxruntime-directml; platform_system == "Windows"
onnxruntime; platform_system == "Darwin"
```

此外，服务端依赖文件没有列出运行时代码直接导入的 `sentencepiece`、`soundfile` 和 `srt`。分别可见 `core/server/engines/sensevoice_onnx/inference/engine.py:6`、`core/server/engines/sensevoice_onnx/inference/audio.py:6` 和 `core/server/engines/qwen_asr_gguf/inference/exporters.py:5`。若客户端和服务端使用独立环境，不能依赖客户端 requirements 偶然补齐这些包；阶段 0 必须先审计并锁定每个引擎的完整依赖闭包。

当前 Qwen、FunASR 和 SenseVoice 的 ONNX wrapper 均已有 `CPUExecutionProvider` 回退路径，因此 CPU MVP 不需要先实现 CoreML，但这只证明代码路径存在，不证明模型已经成功运行。CoreML EP 可以作为后续优化；是否能使用预编译 Python 包、模型算子是否完整支持、是否真正提速，都必须单独验证，不能作为首版承诺。

### 5. 现有文件转录不是无头服务端入口

`start_client.py:3` 会先导入完整 `CapsWriterClient`。`core/client/app.py:21-33` 在判断文件模式前就导入 manager、快捷键和文本输出，构造函数又在 `core/client/app.py:77` 创建 `ShortcutManager`；这会触发 `core/client/shortcut/key_mapper.py:9` 的 Win32 导入。`core/client/manager/__init__.py:4` 同时提前导入 `MicRunner`，后者在 `core/client/manager/mic_runner.py:4` 导入 UI/Tk。

因此，安装 `ffmpeg` 后直接运行现有文件转录仍不能作为 macOS 阶段 0 验收。阶段 0 应增加一个只依赖服务端协议/引擎的固定 WAV 测试工具；现有 FileRunner 则在阶段 1 完成 lazy import 或职责拆分后再验证。

### 6. GGUF 动态库“能加载”不等于“模型已跑通”

项目 loader 已为 Darwin 选择 `.dylib` 文件名，例如 `core/server/engines/qwen_asr_gguf/inference/llama.py:223-225`。审计确认精确版本 `b7798` 的官方 macOS arm64 包包含 loader 需要的库和关键符号。

但发布包内部还有 `libggml-metal.dylib`、`libggml-cpu.dylib`、`libggml-blas.dylib` 等依赖。不能只复制三个显式加载的文件；应保留完整库集、符号链接和 `@rpath` 关系，或集中到一个受控的 native runtime 目录。模型真正加载前仍需验证：

- ctypes wrapper 与 `b7798` ABI 是否完全一致；
- Metal backend 是否实际启用，而非静默回退 CPU；
- 目标支持配置下模型、KV cache、ONNX encoder 和 Python 进程的总峰值；
- 首字延迟、长语音实时率、持续运行稳定性。

### 7. 菜单栏和 UI 生命周期需重做

`core/ui/tray.py:53-56` 显式禁用非 Windows，`core/ui/tray.py:325` 又在线程中调用 `pystray.Icon.run()`。pystray 的 macOS 文档要求 `run()` 位于主线程，因为 Cocoa 需要主运行循环。Windows 控制台窗口的显示/隐藏逻辑也不能复用。

审计所用 Python 运行时未提供 `_tkinter`，而项目 UI/Toast 使用 Tk。最小版本应默认关闭 tray、toast 和 Tk 对话框；产品化阶段再选择固定带 Tk 的 Python 运行时，或将菜单栏和设置界面迁移到原生 Cocoa/Swift 辅助程序。

### 8. 其他需要平台化的细节

- `core/tools/window_detector.py` 的 Darwin 分支主要依赖 AppleScript，且对 Safari/Terminal 做特殊处理；现有配置仍是 `WeiXin.exe` 等 Windows 进程名。应统一成平台无关应用标识，并在 macOS 使用 Bundle ID/进程名。
- 麦克风代码固定以 48 kHz 采样并通过切片降到 16 kHz。多数设备可用，但应查询默认设备能力并提供采样率/声道回退。
- 文件转录依赖外部 `ffmpeg`；审计时尚未安装。
- 现有 PyInstaller spec 使用 `.ico`、Windows DLL 筛选、反斜杠路径和控制台 `.exe` 假设，不能直接作为可发布的 macOS 构建配置。

## 推荐实施计划

### 阶段 0：独立服务端基线

目标：证明 Apple Silicon 上的识别主链路可用。

- 新增独立固定 WAV/WebSocket smoke 工具，不导入 `CapsWriterClient`、快捷键或 UI。
- 将 ONNX Runtime 依赖改为平台条件，并补齐每个引擎的显式依赖闭包。
- 建立 macOS 安装说明和可重复的虚拟环境。
- 优先跑通 Paraformer CPU；SenseVoice CPU 作为补齐依赖后的第二道运行门槛，不预设成功。
- 用固定 WAV 样本记录启动时间、实时率、峰值内存和识别结果。
- 安装 `ffmpeg`，但现有客户端 FileRunner 延后到阶段 1 拆分导入后验证。

验收门槛：10 次预热后连续处理 100 个固定请求且成功率 100%，再持续运行 30 分钟无未处理异常；记录预热后和结束时 RSS，结束值不得超过预热后中位数的 120%。同一固定样本重复三次应得到一致的规范化文本。这里的 120% 是首轮泄漏筛查线，不是最终性能指标。

### 阶段 1：粘贴式客户端 MVP

目标：在任意常见文本框完成“按键录音、松开识别、粘贴结果”。

- 抽象 shortcut 和 synthetic input 平台后端。
- 使用单个 F 功能键，暂不实现组合键，也不抑制 Caps Lock。
- 拆分客户端 eager import，使 FileRunner 不再导入快捷键、MicRunner 或 Tk UI。
- 强制 paste 模式，移除 macOS 路径上的 `keyboard.write` 和私有状态读取。
- 默认关闭 tray、toast、LLM 流式逐字输出和按应用自动行为。
- 增加麦克风、辅助功能、输入监控的权限预检。
- 用 `NSPasteboard` 完整保存/恢复剪贴板多类型数据；若首版不做，必须默认关闭恢复并把限制列为已知风险。

验收门槛：记录测试应用和版本，在 TextEdit、Safari 文本框、微信各执行 30 次输入，每类至少 29 次文本正确且无焦点丢失。若选择完整恢复方案，对纯文本、富文本、图片和文件剪贴板逐类验证恢复后 UTI/数据等价；若选择首版不恢复，配置必须默认关闭恢复、不得执行有损的纯文本备份路径，并把“粘贴会替换剪贴板”列为已知限制。权限缺失时必须在 5 秒内给出可操作错误，而不是静默失效。

### 阶段 2：Caps Lock 与应用集成

目标：恢复 CapsWriter 的核心交互。

- 使用 `darwin_intercept` 或 Quartz Event Tap 实现 Caps Lock 的按下、释放、抑制和短按恢复。
- 增加安全退出和异常后的锁定状态修复。
- 将按应用规则迁移到 Bundle ID/进程名。
- 增加睡眠唤醒、快速切换用户、权限被撤销等测试。

验收门槛：完成至少 200 次短按/长按交替、3 次睡眠唤醒和 3 次进程强制退出恢复测试；不得遗留错误的大写锁定状态，权限缺失或运行中的权限撤销不得静默失效。

### 阶段 3：Qwen/FunASR 与 Metal

目标：在 Apple Silicon 上取得可接受的准确率和延迟。

- 固定 llama.cpp `b7798` arm64 运行时和校验值。
- 集中管理完整 dylib 集，启动时输出实际 backend。
- 下载项目对应模型，分别基准 CPU/Metal。
- 为动态库、模型版本、内存不足和 ABI 错误提供可诊断日志。

验收门槛：日志明确证明 Metal backend 已启用；对至少 20 条短句和 5 条五分钟长音频记录实时率、首字延迟、峰值内存和失败率，再决定默认引擎。此阶段先产出基准，不预设“可接受”的阈值。

### 阶段 4：发布级 `.app`

目标：形成普通用户可安装的版本。

- 新建独立 macOS PyInstaller spec 或原生启动器，不污染 Windows spec。
- 使用 `.icns`，补齐 `Info.plist` 权限说明和稳定 Bundle ID。
- 处理 dylib rpath、签名、Hardened Runtime、公证和首次启动授权流程。
- 将菜单栏生命周期放在主线程，定义更新和卸载策略。

验收门槛：先明确最低支持版本；在最低版本和当前版本各一台未配置开发环境的机器上，安装、首次授权、30 次输入、退出、重启和升级均通过，签名与公证验证无错误。

## Spike 预算

以下仅用于安排可行性 spike，不是交付日期或发布承诺。每阶段通过验收后必须根据实际权限、模型和应用矩阵重新估算；在 Caps Lock、签名应用 TCC 权限和真实模型基准通过前，不应承诺发布日期。假设单名熟悉 Python/macOS 的工程师，不包含模型训练：

| 目标 | 估计 |
| --- | --- |
| 命令行服务端 + Paraformer/SenseVoice CPU 基线 | 2-4 个专注工作日 |
| 普通热键 + 粘贴输出 + 权限提示的可用客户端 | 约 1 周 |
| 可靠 Caps Lock 抑制/恢复和跨应用测试 | 再增加约 1 周 |
| Qwen/FunASR Metal、菜单栏、签名公证、发布体验 | 总计约 3-6 周 |

最大不确定性不是识别算法，而是全局输入权限、Caps Lock 状态机、不同应用的粘贴行为以及最终签名应用的授权稳定性。

## 建议的代码边界

为避免破坏现有 Windows 用户，适配应遵循以下边界：

- 保留 Windows 后端和默认行为，平台差异通过明确 backend/factory 选择。
- 不在业务层散布更多 `platform.system()`；集中到 shortcut、input、window、UI、runtime packaging 边界。
- 首版 macOS 配置采用保守默认值：paste、普通热键、无 tray、CPU 引擎。
- 每个阶段先加入可自动运行的纯逻辑测试，再做需要授权的真实系统集成测试。
- 不向上游创建 PR；所有分支、提交和后续 fork-local PR 仅存在于本 fork。

## 参考资料

- [pynput FAQ：macOS `darwin_intercept` 与事件抑制](https://pynput.readthedocs.io/en/latest/faq.html)
- [pynput 平台限制与 macOS 辅助功能授权](https://pynput.readthedocs.io/en/latest/limitations.html)
- [keyboard 官方仓库的平台支持说明](https://github.com/boppreh/keyboard)
- [Apple：macOS 媒体采集授权](https://developer.apple.com/documentation/bundleresources/requesting-authorization-for-media-capture-on-macos?language=objc)
- [Apple：全局事件监控与辅助功能](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/EventOverview/MonitoringEvents/MonitoringEvents.html)
- [ONNX Runtime CoreML Execution Provider](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)
- [pystray：macOS 主线程要求](https://pystray.readthedocs.io/en/latest/usage.html)
- [llama.cpp `b7798` 发布](https://github.com/ggml-org/llama.cpp/releases/tag/b7798)
- [PyInstaller macOS bundle 选项](https://pyinstaller.org/en/stable/usage.html)
