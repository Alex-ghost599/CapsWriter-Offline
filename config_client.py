import os
import sys
from pathlib import Path

# 版本信息
__version__ = '2.6'

def _default_base_dir() -> Path:
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        return Path.home() / 'Library' / 'Application Support' / 'CapsWriter-Offline'
    return Path(__file__).resolve().parent


def _macos_shortcut_key() -> str:
    return os.environ.get('CAPSWRITER_HOTKEY', 'shift_r').strip() or 'shift_r'


# 源码运行时使用仓库目录；macOS App 使用可写的 Application Support 目录。
BASE_DIR = str(Path(os.environ.get('CAPSWRITER_HOME', _default_base_dir())).expanduser().resolve())
Path(BASE_DIR).mkdir(parents=True, exist_ok=True)


# 客户端配置
class ClientConfig:
    addr = os.environ.get('CAPSWRITER_SERVER_ADDR', '127.0.0.1')
    port = os.environ.get('CAPSWRITER_SERVER_PORT', '6016')

    # 快捷键配置列表
    shortcuts = (
        [
            {
                'key': _macos_shortcut_key(),
                'type': 'keyboard',
                'suppress': False,
                'hold_mode': True,
                'enabled': True,
            },
        ]
        if sys.platform == 'darwin'
        else [
            {
                'key': 'caps_lock',     # 监听大写锁定键
                'type': 'keyboard',     # 是键盘快捷键
                'suppress': True,       # 阻塞按键（短按会补发）
                'hold_mode': True,      # 长按模式
                'enabled': True         # 启用此快捷键
            },
            {
                'key': 'x2',
                'type': 'mouse',
                'suppress': True,
                'hold_mode': True,
                'enabled': True
            },
        ]
    )

    threshold    = 0.3          # 快捷键触发阈值（秒）

    paste        = sys.platform == 'darwin'  # macOS 使用剪贴板与 Command-V 输出
    restore_clip = True         # 模拟粘贴后是否恢复剪贴板
    paste_apps   = [] if sys.platform == 'darwin' else ['WeiXin.exe', 'Telegram.exe']

    enter_apps   = [] if sys.platform == 'darwin' else [('happ.exe', 0.5), ('hexin.exe', 0.5)]

    save_audio = True           # 是否保存录音文件
    audio_name_len = 20         # 将录音识别结果的前多少个字存储到录音文件名中，建议不要超过200
    
    context = ''                # 提示词上下文，用于辅助 Fun-ASR-Nano 模型识别（例如输入人名、地名、专业术语等）
    language = 'auto'           # 识别语言：'auto', 'chinese', 'english', 'japanese' 等（各引擎支持范围不同）

    trash_punc = '，。,.'       # 识别结果要消除的末尾标点
    trash_punc_thresh = 8       # 识别结果的单词数量低于阈值时，强制去除末尾标点
    trash_punc_apps = [] if sys.platform == 'darwin' else ['WeiXin.exe', ]

    traditional_convert = False     # 是否将识别结果转换为繁体中文
    traditional_locale = 'zh-hant'  # 繁体地区：'zh-hant'（标准繁体）, 'zh-tw'（台湾繁体）, 'zh-hk'（香港繁体）

    hot = True                 # 是否启用热词替换（统一 RAG 匹配）
    hot_thresh = 0.85           # RAG 替换热词阈值（高阈值，用于实际替换）
    hot_similar = 0.6           # RAG 相似热词阈值（低阈值，用于 LLM 上下文）
    hot_rule = True             # 是否启用自定义规则替换（基于正则表达式）

    llm_enabled = sys.platform != 'darwin'  # macOS 首版先验证离线 ASR 主链路
    llm_stop_key = 'esc'        # 中断 LLM 输出的快捷键

    enable_tray = sys.platform == 'win32'  # 当前托盘生命周期仅适配 Windows

    # 日志配置
    log_level = 'DEBUG'          # 日志级别：'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    mic_seg_duration = 60       # 麦克风听写时分段长度：60秒
    mic_seg_overlap = 4         # 麦克风听写时分段重叠：4秒
    audio_device = os.environ.get('CAPSWRITER_AUDIO_DEVICE') or None
    if isinstance(audio_device, str) and audio_device.isdigit():
        audio_device = int(audio_device)
    audio_sample_rate = int(os.environ.get('CAPSWRITER_AUDIO_SAMPLE_RATE', '48000'))

    file_seg_duration = 60      # 转录文件时分段长度
    file_seg_overlap = 4        # 转录文件时分段重叠

    file_save_srt = True        # 转录文件时是否保存 srt 字幕
    file_save_txt = True        # 转录文件时是否保存 txt 文本（按标点切分后的）
    file_save_json = True       # 转录文件时是否保存 json 结果（含原始时间戳）
    file_save_merge = False      # 转录文件时是否保存 merge.txt（未切分的段落长文本）

    udp_broadcast = False               # 是否启用 UDP 广播输出结果
    udp_broadcast_targets = [           # UDP 广播目标地址列表，格式: (地址, 端口)
        ('127.255.255.255', 6017),      # 本地回环广播
        # ('192.168.1.255', 6017),      # 局域网广播（示例，按需启用）
    ]

    udp_control = False             # 是否启用 UDP 控制录音（外部程序发送 START/STOP 命令）
    udp_control_addr = '127.0.0.1'  # UDP 控制监听地址（'0.0.0.0' 允许外部访问）
    udp_control_port = 6018         # UDP 控制监听端口


# 快捷键配置说明
r"""
快捷键配置字段说明：
  key        - 按键名称（见下方可用按键列表）
  type       - 输入类型：'keyboard'（键盘）或 'mouse'（鼠标）
  suppress   - 是否阻塞按键（True=阻塞，False=不阻塞）
  hold_mode  - 长按模式（True=按下录音松开停止，False=单击开始再次单击停止）
  enabled    - 是否启用此快捷键

阻塞模式说明：
  - 阻塞模式  ：长按录音识别，短按（<0.3秒）则自动补发按键，不影响单击功能
  - 非阻塞模式：对于 CapsLock/NumLock/ScrollLock 这类切换键，松开时会自动补发，以恢复按键状态

可用按键名称：

  字母数字：a - z, 0 - 9（大键盘）

  符号键：, . / \ ` ' - = [ ] ; '


  功能键：f1 - f24

  控制键:
      ctrl_l,   ctrl_r,
      shift,  shift_r,
      alt_l,    alt_gr,
      cmd,    cmd_r

  特殊键：
      space, enter, tab, backspace, delete, insert, home, end
      page_up, page_down, esc, caps_lock, num_lock, scroll_lock
      print_screen, pause, menu

  方向键：up, down, left, right

  鼠标键：x1, x2

示例配置：
  {'key': 'caps_lock', 'type': 'keyboard', 'suppress': False, 'hold_mode': True, 'enabled': True}, 
  {'key': 'f12', 'type': 'keyboard', 'suppress': True, 'hold_mode': True, 'enabled': True}, 
  {'key': 'x2', 'type': 'mouse', 'suppress': True, 'hold_mode': True, 'enabled': True}, 
"""
