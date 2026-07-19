#!/usr/bin/env bash
set -euo pipefail

uv run ruff check \
  config_client.py \
  config_server.py \
  core/client/__init__.py \
  core/client/app.py \
  core/client/audio/file_manager.py \
  core/client/audio/recorder.py \
  core/client/audio/stream.py \
  core/client/clipboard/clipboard.py \
  core/client/llm/llm_get_selection.py \
  core/client/llm/llm_output_typing.py \
  core/client/macos_permissions.py \
  core/client/manager/file_runner.py \
  core/client/manager/mic_runner.py \
  core/client/output/result_processor.py \
  core/client/output/text_output.py \
  core/client/platform_input.py \
  core/client/shortcut/key_mapper.py \
  core/client/shortcut/shortcut_manager.py \
  core/client/state.py \
  core/client/transcribe/media_tool.py \
  core/client/ui/tips.py \
  core/server/connection/server_manager.py \
  core/server/connection/ws_recv.py \
  core/server/engines/ct_transformer/punc_engine.py \
  core/server/engines/paraformer_onnx/asr_engine.py \
  core/server/engines/sherpa_runtime.py \
  core/server/worker/model_loader.py \
  core/tools/external_tools.py \
  scripts/download_macos_models.py \
  tests
