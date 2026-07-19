from types import SimpleNamespace

from core.client.manager import mic_runner


class StartedResource:
    def __init__(self, result=None):
        self.result = result
        self.started = False

    def start(self):
        self.started = True
        return self.result


def test_disabled_llm_monitor_is_not_started(monkeypatch):
    stream = StartedResource(result=object())
    llm = StartedResource()
    app = SimpleNamespace(
        state=SimpleNamespace(),
        ws=SimpleNamespace(),
        tray=StartedResource(),
        stream=stream,
        shortcut=StartedResource(),
        udp=StartedResource(),
        hotword=StartedResource(),
        llm=llm,
    )
    monkeypatch.setattr(mic_runner.sys, 'platform', 'linux')
    monkeypatch.setattr(mic_runner.Config, 'llm_enabled', False)
    monkeypatch.setattr(mic_runner.Config, 'udp_control', False)
    monkeypatch.setattr(mic_runner.TipsDisplay, 'show_mic_tips', lambda: None)

    mic_runner.MicRunner(app).start_resources()

    assert stream.started
    assert not llm.started
