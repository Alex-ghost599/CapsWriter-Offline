import io
from pathlib import Path

import pytest

from core.client import app as client_app
from core.client.manager import file_runner


_resolve_input_files = client_app._resolve_input_files


def test_non_interactive_stdin_does_not_require_pause(monkeypatch):
    monkeypatch.setattr(file_runner.sys, 'stdin', io.StringIO())

    assert not file_runner._has_interactive_stdin()


def test_relative_input_file_is_resolved_from_launch_directory(tmp_path):
    audio = tmp_path / 'input.wav'
    audio.write_bytes(b'wave')

    assert _resolve_input_files(['input.wav'], tmp_path) == [audio.resolve()]
    assert _resolve_input_files(['missing.wav'], tmp_path) == []


@pytest.mark.parametrize('error', [OSError('bad path'), RuntimeError('symlink loop')])
def test_unresolvable_input_path_is_ignored_and_valid_file_continues(
    tmp_path, monkeypatch, error
):
    original_resolve = Path.resolve
    warnings = []
    audio = tmp_path / 'input.wav'
    audio.write_bytes(b'wave')

    def resolve(path, *args, **kwargs):
        if path.name == 'loop':
            raise error
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', resolve)
    monkeypatch.setattr(client_app.logger, 'warning', warnings.append)

    assert _resolve_input_files(['loop', 'input.wav'], tmp_path) == [audio.resolve()]
    assert len(warnings) == 1
    assert "'loop'" in warnings[0]


def test_expanduser_failure_is_ignored(tmp_path, monkeypatch):
    original_expanduser = Path.expanduser
    warnings = []

    def expanduser(path):
        if path.name == '~missing-user':
            raise RuntimeError('unknown user')
        return original_expanduser(path)

    monkeypatch.setattr(Path, 'expanduser', expanduser)
    monkeypatch.setattr(client_app.logger, 'warning', warnings.append)

    assert _resolve_input_files(['~missing-user'], tmp_path) == []
    assert len(warnings) == 1
