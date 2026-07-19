"""Resolve external command-line tools across source and bundled app launches."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def find_executable(name: str) -> str | None:
    """Find a tool, including Homebrew paths omitted from Finder-launched apps."""
    override = os.environ.get(f'CAPSWRITER_{name.upper()}')
    if override:
        override_path = Path(override).expanduser()
        if override_path.is_file() and os.access(override_path, os.X_OK):
            return str(override_path.resolve())

    resolved = shutil.which(name)
    if resolved:
        return resolved

    if sys.platform == 'darwin':
        for directory in (Path('/opt/homebrew/bin'), Path('/usr/local/bin')):
            candidate = directory / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None
