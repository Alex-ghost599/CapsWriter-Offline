from pathlib import Path

from core.server.engines.sherpa_runtime import ensure_sherpa_onnx_runtime


def test_macos_sherpa_runtime_is_resolvable():
    target = ensure_sherpa_onnx_runtime()

    if target is not None:
        assert isinstance(target, Path)
        assert target.exists()
        assert target.resolve().name.startswith("libonnxruntime.")
