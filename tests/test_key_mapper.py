from pynput import keyboard

from core.client.shortcut.key_mapper import KeyMapper


def test_function_key_name_is_platform_neutral():
    assert KeyMapper.key_to_name(keyboard.Key.f8) == "f8"


def test_character_key_name_is_normalized():
    assert KeyMapper.key_to_name(keyboard.KeyCode.from_char("A")) == "a"
