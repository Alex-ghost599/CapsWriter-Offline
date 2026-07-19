import runpy
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config_client
from core.client import platform_input
from core.client.clipboard import clipboard
from core.client.llm import llm_get_selection
from core.client.ui.tips import _format_shortcut_name


class FakeController:
    def __init__(self):
        self.modifiers = []
        self.tapped = []

    @contextmanager
    def pressed(self, modifier):
        self.modifiers.append(modifier)
        yield

    def tap(self, key):
        self.tapped.append(key)


def test_windows_primary_shortcut_uses_control(monkeypatch):
    controller = FakeController()
    monkeypatch.setattr(platform_input.sys, 'platform', 'win32')
    monkeypatch.setattr(platform_input, '_controller', lambda: controller)

    platform_input.send_primary_shortcut('v')

    assert controller.modifiers == [platform_input.keyboard.Key.ctrl]
    assert controller.tapped == ['v']


@pytest.mark.asyncio
async def test_windows_paste_restores_clipboard(monkeypatch):
    copied = []
    paste_shortcut = Mock()

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(clipboard.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(clipboard, 'safe_paste', lambda: 'original')
    monkeypatch.setattr(clipboard.pyclip, 'copy', copied.append)
    monkeypatch.setattr(clipboard, 'send_paste_shortcut', paste_shortcut)
    monkeypatch.setattr(clipboard.asyncio, 'sleep', no_sleep)

    await clipboard.paste_text('recognized', restore_clipboard=True)

    assert copied == ['recognized', 'original']
    paste_shortcut.assert_called_once_with()


def test_llm_selection_uses_platform_copy_and_restores_clipboard(monkeypatch):
    clipboard_values = iter(('original', 'selected text'))
    copied = []
    copy_shortcut = Mock()
    role = SimpleNamespace(
        enable_read_selection=True,
        name='assistant',
        selection_max_length=1000,
        enable_history=False,
    )
    state = SimpleNamespace(last_output_text='previous output')
    monkeypatch.setattr(llm_get_selection, 'safe_paste', lambda: next(clipboard_values))
    monkeypatch.setattr(llm_get_selection.pyclip, 'copy', copied.append)
    monkeypatch.setattr(llm_get_selection, 'send_copy_shortcut', copy_shortcut)
    monkeypatch.setattr(llm_get_selection.time, 'sleep', lambda _seconds: None)

    assert llm_get_selection.get_selected_text(role, state) == 'selected text'
    assert copied == ['original']
    copy_shortcut.assert_called_once_with()


def test_macos_shortcut_environment_override(monkeypatch):
    monkeypatch.setenv('CAPSWRITER_HOTKEY', 'f10')
    assert config_client._macos_shortcut_key() == 'f10'

    monkeypatch.setenv('CAPSWRITER_HOTKEY', '')
    assert config_client._macos_shortcut_key() == 'shift_r'


def test_hotkey_environment_override_is_macos_only(monkeypatch):
    monkeypatch.setenv('CAPSWRITER_HOTKEY', 'f10')
    monkeypatch.setattr(sys, 'platform', 'win32')

    namespace = runpy.run_path(config_client.__file__)

    assert [item['key'] for item in namespace['ClientConfig'].shortcuts] == ['caps_lock', 'x2']


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS shortcut defaults')
def test_macos_defaults_to_right_shift():
    from config_client import ClientConfig as Config

    assert Config.shortcuts == [
        {
            'key': 'shift_r',
            'type': 'keyboard',
            'suppress': False,
            'hold_mode': True,
            'enabled': True,
        },
    ]


def test_directional_modifier_display_name():
    assert _format_shortcut_name('shift_r') == 'Right Shift'


@pytest.mark.skipif(sys.platform != 'win32', reason='native Win32 filter regression')
def test_windows_defaults_and_native_filters():
    from config_client import ClientConfig as Config
    from core.client.shortcut.key_mapper import WM_KEYDOWN, WM_XBUTTONDOWN, XBUTTON2
    from core.client.shortcut.shortcut_manager import ShortcutManager
    from pynput import keyboard

    assert [(item['key'], item['type']) for item in Config.shortcuts] == [
        ('caps_lock', 'keyboard'),
        ('x2', 'mouse'),
    ]
    assert Config.llm_enabled and Config.enable_tray and not Config.paste

    manager = ShortcutManager.__new__(ShortcutManager)
    manager._check_emulating = Mock(return_value=False)
    manager._check_restoring = Mock(return_value=False)
    manager._event_handler = SimpleNamespace(handle_keydown=Mock(), handle_keyup=Mock())
    manager._handle_mouse_keyup = Mock()
    manager.keyboard_listener = SimpleNamespace(suppress_event=Mock())
    manager.mouse_listener = SimpleNamespace(suppress_event=Mock())

    caps_task = SimpleNamespace(shortcut=SimpleNamespace(suppress=True))
    manager.tasks = {'caps_lock': caps_task}
    keyboard_filter = manager.create_keyboard_filter()
    keyboard_filter(WM_KEYDOWN, SimpleNamespace(vkCode=keyboard.Key.caps_lock.value.vk))
    manager._event_handler.handle_keydown.assert_called_once_with('caps_lock', caps_task)
    manager.keyboard_listener.suppress_event.assert_called_once_with()

    x2_task = SimpleNamespace(shortcut=SimpleNamespace(suppress=True))
    manager.tasks = {'x2': x2_task}
    mouse_filter = manager.create_mouse_filter()
    mouse_filter(WM_XBUTTONDOWN, SimpleNamespace(mouseData=XBUTTON2 << 16))
    manager._event_handler.handle_keydown.assert_called_with('x2', x2_task)
    manager.mouse_listener.suppress_event.assert_called_once_with()
