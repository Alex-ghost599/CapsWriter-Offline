"""Platform-neutral synthetic keyboard input."""

from __future__ import annotations

import sys

from pynput import keyboard


def _controller() -> keyboard.Controller:
    return keyboard.Controller()


def send_primary_shortcut(character: str) -> None:
    """Send Command+character on macOS and Ctrl+character elsewhere."""
    modifier = keyboard.Key.cmd if sys.platform == 'darwin' else keyboard.Key.ctrl
    controller = _controller()
    with controller.pressed(modifier):
        controller.tap(character)


def send_copy_shortcut() -> None:
    send_primary_shortcut('c')


def send_paste_shortcut() -> None:
    send_primary_shortcut('v')


def tap_key(key_name: str) -> None:
    special_keys = {
        'enter': keyboard.Key.enter,
        'esc': keyboard.Key.esc,
        'tab': keyboard.Key.tab,
        'space': keyboard.Key.space,
    }
    key = special_keys.get(key_name, key_name)
    _controller().tap(key)
