"""Runtime compatibility helpers for sherpa-onnx."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path


def ensure_sherpa_onnx_runtime() -> Path | None:
    """Expose ONNX Runtime's dylib at the rpath used by sherpa-onnx on macOS."""
    if sys.platform != "darwin":
        return None

    sherpa_spec = find_spec("sherpa_onnx")
    ort_spec = find_spec("onnxruntime")
    if sherpa_spec is None or sherpa_spec.origin is None:
        raise RuntimeError("sherpa-onnx is not installed; run `uv sync --all-groups`")
    if ort_spec is None or ort_spec.origin is None:
        raise RuntimeError("onnxruntime is not installed; run `uv sync --all-groups`")

    sherpa_lib = Path(sherpa_spec.origin).parent / "lib"
    ort_capi = Path(ort_spec.origin).parent / "capi"
    ort_version = version('onnxruntime')
    source = ort_capi / f'libonnxruntime.{ort_version}.dylib'
    if not source.is_file():
        raise RuntimeError(f"ONNX Runtime {ort_version} dylib was not found at {source}")
    target = sherpa_lib / source.name
    if target.is_symlink() or target.exists():
        if target.resolve() != source.resolve():
            raise RuntimeError(f"Unexpected ONNX Runtime library already exists at {target}")
        return target

    try:
        target.symlink_to(Path(os.path.relpath(source, sherpa_lib)))
    except OSError as exc:
        raise RuntimeError(
            "Unable to prepare sherpa-onnx's macOS runtime. "
            "Ensure the uv environment is writable and run the command again."
        ) from exc
    return target


def load_sherpa_onnx():
    ensure_sherpa_onnx_runtime()
    return import_module('sherpa_onnx')
