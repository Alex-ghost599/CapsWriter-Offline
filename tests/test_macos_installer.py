import platform
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != 'darwin' or platform.machine() != 'arm64',
    reason='macOS source installer requires Apple Silicon',
)

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'install_macos.sh'


def run_installer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['bash', str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_installer_help():
    result = run_installer('--help')

    assert result.returncode == 0
    assert '--skip-models' in result.stdout
    assert '--dry-run' in result.stdout


def test_installer_dry_run_is_non_destructive(tmp_path: Path):
    install_dir = tmp_path / 'CapsWriter Offline'

    result = run_installer(
        '--dry-run',
        '--skip-system-deps',
        '--skip-models',
        '--skip-build',
        '--install-dir',
        str(install_dir),
    )

    assert result.returncode == 0, result.stderr
    assert 'git clone' in result.stdout
    assert 'uv sync --all-groups --frozen' in result.stdout
    assert 'Skipping model download' in result.stdout
    assert 'Skipping client build' in result.stdout
    assert not install_dir.exists()


def test_installer_rejects_unknown_option():
    result = run_installer('--not-an-option')

    assert result.returncode == 2
    assert 'Unknown option: --not-an-option' in result.stderr
