import os
from pathlib import Path

from core.tools.external_tools import find_executable


def test_find_executable_uses_explicit_override(tmp_path: Path, monkeypatch):
    executable = tmp_path / 'ffmpeg-custom'
    executable.write_text('#!/bin/sh\n', encoding='utf-8')
    executable.chmod(0o755)
    monkeypatch.setenv('CAPSWRITER_FFMPEG', str(executable))

    assert find_executable('ffmpeg') == str(executable.resolve())


def test_find_executable_rejects_non_executable_override(tmp_path: Path, monkeypatch):
    candidate = tmp_path / 'ffmpeg-custom'
    candidate.write_text('not executable', encoding='utf-8')
    candidate.chmod(0o644)
    monkeypatch.setenv('CAPSWRITER_FFMPEG', str(candidate))
    monkeypatch.setenv('PATH', '')

    resolved = find_executable('ffmpeg')

    if resolved is not None:
        assert os.access(resolved, os.X_OK)
