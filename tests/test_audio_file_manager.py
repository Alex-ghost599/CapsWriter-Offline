from pathlib import Path

from core.client.audio import file_manager


class FakeStdin:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakePopen:
    def __init__(self, return_code=0):
        self.stdin = FakeStdin()
        self.wait_calls = []
        self.return_code = return_code

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.return_code


class TimeoutPopen(FakePopen):
    def __init__(self):
        super().__init__()
        self.kill_calls = 0

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if timeout is not None:
            raise file_manager.TimeoutExpired('ffmpeg', timeout)
        return -9

    def kill(self):
        self.kill_calls += 1


def test_finish_waits_for_ffmpeg_before_returning(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(file_manager, 'Popen', FakePopen)
    process = FakePopen()
    manager = file_manager.AudioFileManager()
    manager.file_handle = process
    manager.file_path = tmp_path / 'recording.mp3'

    assert manager.finish() == manager.file_path
    assert process.stdin.closed
    assert process.wait_calls == [10]


def test_finish_returns_none_and_removes_failed_ffmpeg_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(file_manager, 'Popen', FakePopen)
    process = FakePopen(return_code=1)
    output = tmp_path / 'recording.mp3'
    output.write_bytes(b'incomplete')
    manager = file_manager.AudioFileManager()
    manager.file_handle = process
    manager.file_path = output

    assert manager.finish() is None
    assert not output.exists()
    assert manager.file_handle is None


def test_finish_kills_timed_out_ffmpeg_and_removes_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(file_manager, 'Popen', TimeoutPopen)
    process = TimeoutPopen()
    output = tmp_path / 'recording.mp3'
    output.write_bytes(b'incomplete')
    manager = file_manager.AudioFileManager()
    manager.file_handle = process
    manager.file_path = output

    assert manager.finish() is None
    assert process.kill_calls == 1
    assert process.wait_calls == [10, None]
    assert not output.exists()
    assert manager.file_handle is None
