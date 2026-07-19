# macOS 运行验证记录

验证日期：2026-07-19

## 环境

- Apple Silicon Mac，arm64
- macOS 15.x
- Python 3.12.13，由 `uv 0.11.29` 管理
- FFmpeg 8.1.2（Homebrew）
- sherpa-onnx 1.13.4，onnxruntime 1.27.0，soxr 1.1.0
- Paraformer + Punct-CT-Transformer 官方模型

## 模型与文件链路

官方 Release ZIP 校验结果：

```text
Paraformer.zip
a12a3f9791483329441c94ad759cbcf258d7246784a6d368cd3c591add4d888b

Punct-CT-Transformer.zip
de106e6cf13764bd3124f31864bc30158f04961788765b63262bdd5ba21fa421
```

模型自带 `asr_example.wav` 为 16 kHz、13.052 秒真实语音。直接加载 Paraformer
约 0.89 秒，解码约 0.23 秒，直接推理进程最大 RSS 约 595 MB。完整服务端 +
WebSocket 文件转录输出：

```text
正是因为存在绝对正义，所以我们接受现实的相对正义，但是不要因为现实的相对正义，
我们就认为这个世界没有正义。因为如果当你认为这个世界没有正义。
```

这一路径使用真实模型与真实 WAV，不是 mock 或协议 smoke。
安全加固后服务端实际只监听 `127.0.0.1:6016`；同一真实 WAV 在帧、分段、
缓冲和连接上限启用后仍于 0.28 秒转写成功。999 秒的非法分段请求被实际
WebSocket 以关闭码 `1008` 拒绝。

## 实时输入链路

第一轮已授权的构建产物 `dist/CapsWriter.app`：

- 114 MB
- Mach-O arm64
- Bundle ID：`io.github.alex-ghost599.capswriter-offline.client`
- PyInstaller ad-hoc 深度签名校验通过
- 运行数据：`~/Library/Application Support/CapsWriter-Offline`

右 Shift 默认值固化后的最终精确产物为 77 MB、Mach-O arm64，Bundle ID 保持不变，
ad-hoc CDHash 为 `ebea3514cb47c29818a3c44b213a48d8bbcf1a79`。
`codesign --verify --deep --strict` 通过，bundle 内同时包含 soxr 与 PortAudio。启动时明确
移除了 `CAPSWRITER_HOTKEY` 环境变量，控制台仍显示默认快捷键 `Right Shift`。

在 CapsWriter 的麦克风、辅助功能和事件权限获批后，最终构建成功建立：

1. USB 物理麦克风的 48 kHz、单声道 CoreAudio 输入流
2. 全局右 Shift 按下/释放监听
3. `ws://127.0.0.1:6016` 连接
4. 48 kHz 到 16 kHz 的单声道重采样
5. Paraformer 真实推理和标点恢复
6. Command-V 前台应用注入
7. 多类型剪贴板恢复

验收使用右 Shift 和 USB 物理麦克风完成真人说话测试。最终精确 bundle 的 TextEdit
录音为 2.20 秒，转录时延 0.07 秒；Chrome 录音为 1.95 秒，转录时延 0.06 秒。两段
非个人化测试短句均正确写入目标输入框，录音均保存为 48 kHz、单声道 MP3。客户端日志、
服务端 Paraformer 输出、前台应用 AX 值和落盘音频四类证据一致。公开记录不包含设备
品牌、用户路径、录音内容或其他个人标识。

最终文本已实际写入：

- TextEdit 正文
- Google Chrome 新标签页地址栏（未提交导航，验收后已清空）

验收前将剪贴板设为固定探针值；两次识别输出后 `pbpaste` 均返回原探针，证明自动
恢复没有覆盖为识别文本。

44.1 kHz 与 48 kHz 的连续信号均按 50 ms 块送入 `soxr.ResampleStream`，刷新后
与整段 HQ soxr 参考同为 16,000 个采样，当前最大逐样本误差为 0。
这项修正已随最终 bundle 通过右 Shift、物理 CoreAudio、Paraformer 和前台上屏全链路
复验。

最终打包态文件模式已从仓库目录接收相对 WAV 路径，正确解析到同一 13.052 秒
真实文件并完成转写，处理耗时 0.28 秒，在无交互 stdin 时以退出码 0 结束。
最终包还实际接收了不存在的 `~用户` 路径：先记录 warning 并跳过，再继续处理有效
相对 WAV。符号链接循环及 `OSError` 也有回归测试，不会使客户端启动崩溃。
Finder 路径解析在独立 44.1 kHz 双声道
编码中找到 `/opt/homebrew/bin/ffmpeg`，等待编码器成功退出后生成 25,748 字节 MP3。
最终 bundle 的实时录音 MP3 已通过上述物理麦克风验收。

## 可复现环境

以下项目级检查已通过：

```text
uv lock --check
bash scripts/lint_macos_port.sh
uv run pytest -q
git diff --check
```

结果：39 passed, 1 skipped，跳过项为只能在 Windows 执行的原生 Win32 filter
回归。所有本分支新增/修改 Python 文件 Ruff 通过。另在 `/tmp` 创建独立
`UV_PROJECT_ENVIRONMENT`，执行 `uv sync --all-groups --frozen`；项目运行时加载器修复上游
sherpa-onnx wheel 的 macOS rpath 后成功导入 sherpa-onnx 1.13.4 与 soxr 1.1.0，
真实 Paraformer 推理输出包含“正义”。仓库全量
Ruff 仍有 930 个上游既有问题，主要来自未改的实验脚本、UI 和 notebooks，
本适配不批量改写这些文件。

fork 分支已配置 `windows-latest` 回归，覆盖 uv 冻结安装、客户端导入、
CapsLock/X2 Win32 filter、Ctrl-V 剪贴板恢复与 LLM Ctrl-C 选区路径。最终结果以
匿名化历史重建后的 fork-local PR checks 为准，不在公开文档中保留已清理提交的标识。

独立 reviewer 对目标、平台边界、安全限制、失败模式和证据质量完成多轮复核，
最终结论为 PASS，未发现未关闭 High/Medium。FFmpeg 超时分支现已覆盖
`kill -> wait -> 删除残件 -> None`；剩余 Low 是剪贴板 changeCount 检查后仍存在
极小的系统级 TOCTOU 窗口。

## 未关闭门槛

- 当前 bundle 使用 ad-hoc 签名，仅适合本机手动构建与授权；正式分发仍需要稳定的
  Developer ID 签名与 Apple 公证。
- macOS 原生事件 API 无法可靠提供 Caps Lock 的物理按下/释放时长，因此本 fork 默认
  使用右 Shift。若必须使用 Caps Lock 长按，需要额外键盘重映射/驱动层支持。
