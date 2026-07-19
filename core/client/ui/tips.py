# coding: utf-8
"""
提示信息显示模块

提供 TipsDisplay 类用于显示启动提示信息。
"""

from __future__ import annotations

import os
import sys

from rich.markdown import Markdown

from core.client.state import console
from config_client import ClientConfig as Config, __version__
from . import logger



def _format_shortcut_name(key: str) -> str:
    """
    格式化快捷键名称用于显示

    Args:
        key: 快捷键名称（如 'caps_lock', 'f12'）

    Returns:
        str: 格式化后的名称（如 'CapsLock', 'F12'）
    """
    directional_modifiers = {
        'shift_l': 'Left Shift',
        'shift_r': 'Right Shift',
        'ctrl_l': 'Left Control',
        'ctrl_r': 'Right Control',
        'alt_l': 'Left Option',
        'alt_r': 'Right Option',
        'cmd_l': 'Left Command',
        'cmd_r': 'Right Command',
    }
    if key in directional_modifiers:
        return directional_modifiers[key]

    return key.replace('_', ' ').title()


def _get_shortcuts_display() -> str:
    """
    获取所有启用快捷键的显示字符串

    Returns:
        str: 格式化的快捷键列表，用逗号分隔
    """
    enabled_shortcuts = [sc for sc in Config.shortcuts if sc.get('enabled', True)]
    if not enabled_shortcuts:
        return '未配置快捷键'

    # 格式化每个快捷键名称
    formatted = [_format_shortcut_name(sc['key']) for sc in enabled_shortcuts]
    return '、'.join(formatted)


class TipsDisplay:
    """
    提示信息显示器
    
    显示客户端启动时的提示信息。
    """
    
    @staticmethod
    def show_mic_tips() -> None:
        """显示麦克风模式的启动提示"""
        shortcuts_display = _get_shortcuts_display()

        console.rule('[bold #d55252]CapsWriter Offline Client[/]')
        console.print(f'\n版本：[bold green]{__version__}[/]')

        if sys.platform == 'darwin':
            platform_intro = '**CapsWriter-Offline** 是一个完全离线的 macOS 语音输入工具。'
            launch_step = '运行 `uv run python start_client.py` 或 **CapsWriter.app**，它负责听音和打字上屏。'
            permission_note = '首次运行需在系统设置中允许麦克风、辅助功能和输入监控权限。'
            privilege_note = f'macOS 当前使用 {shortcuts_display} 长按录音，并通过剪贴板与 Command-V 输入结果。'
        else:
            platform_intro = '**CapsWriter-Offline** 是一个专为 Windows 打造的完全离线语音输入工具。'
            launch_step = '运行 **Client** 端，它作为「耳朵」负责听音和打字上屏。'
            permission_note = '如需在管理员权限运行的程序中输入，请以管理员权限运行客户端。'
            privilege_note = '将音视频文件拖动到 **Client** 端 exe 文件后松开，可转录生成字幕。'

        markdown = f'''

项目地址：https://github.com/Alex-ghost599/CapsWriter-Offline-macOS

{platform_intro}

使用步骤：

1. 运行 **Server** 端，它作为「大脑」负责 AI 推理，约占用 1.5G 内存。
2. {launch_step}
3. 按住快捷键（`{shortcuts_display}`）说话，松开即输入。
4. {privilege_note}


特性：

1. **快、准、稳**：完全离线运行，响应极快，支持自动标点、数字 ITN 和中英间距调整。
2. **热词系统**：支持 `hot.txt` 音素级模糊匹配，准确替换专业术语，支持中英。
3. **正则替换**：支持 `hot-rule.txt` 强制替换规则。
4. **LLM 助手**：支持调用大语言模型，用于润色、翻译、代码助手等角色，可配置读取选中文字。
5. **日记归档**：自动归档每日语音记录及其识别结果。
6. **托盘管理**：右键托盘图标可快速切换模型、修改配置、查看日志或隐藏黑窗口。


注意事项：

1. 当前快捷键：`{shortcuts_display}`，可在 `config_client.py` 中修改。
2. {permission_note}
3. 识别结果默认去除末尾逗句号。
4. 录音保存功能：若检测到 `FFmpeg`，会以 `mp3` 压缩保存；否则保存为 `wav` 。
        '''

        console.print(Markdown(markdown), highlight=True)
        console.rule()
        console.print(f'\n当前基文件夹：[cyan underline]{os.getcwd()}[/]')
        console.print(f'\n服务端地址： [cyan underline]{Config.addr}:{Config.port}[/]')
        console.print(f'\n当前所用快捷键：[green4]{shortcuts_display}[/]')
        console.line()

        logger.debug("已显示麦克风模式启动提示")
    
    @staticmethod
    def show_file_tips() -> None:
        """显示文件转录模式的启动提示"""
        console.print(f'\n版本：[bold green]{__version__}[/]')

        markdown = '\n项目地址：https://github.com/Alex-ghost599/CapsWriter-Offline-macOS'
        console.print(Markdown(markdown), highlight=True)
        console.print(f'当前基文件夹：[cyan underline]{os.getcwd()}[/]')
        console.print(f'服务端地址： [cyan underline]{Config.addr}:{Config.port}[/]')
        
        logger.debug("已显示文件转录模式启动提示")
