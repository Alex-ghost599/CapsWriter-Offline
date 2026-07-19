import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != 'darwin',
    reason='macOS source installer tests run in the dedicated macOS job',
)

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'install_macos.sh'


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding='utf-8')
    path.chmod(0o755)


def installer_env(tmp_path: Path, tools: dict[str, str] | None = None) -> dict[str, str]:
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    write_executable(
        fake_bin / 'uname',
        """#!/bin/bash
case "$1" in
    -s) printf 'Darwin\\n' ;;
    -m) printf 'arm64\\n' ;;
    *) exit 2 ;;
esac
""",
    )
    for name, contents in (tools or {}).items():
        write_executable(fake_bin / name, contents)

    environment = os.environ.copy()
    environment['PATH'] = f'{fake_bin}:{environment["PATH"]}'
    return environment


def run_installer(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['/bin/bash', str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
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
        env=installer_env(tmp_path),
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


def test_installer_rejects_an_option_as_a_value():
    result = run_installer('--install-dir', '--skip-models')

    assert result.returncode == 1
    assert '--install-dir requires a value, not another option' in result.stderr


def test_existing_directory_is_rejected_before_homebrew(tmp_path: Path):
    install_dir = tmp_path / 'existing'
    install_dir.mkdir()
    brew_marker = tmp_path / 'brew-ran'
    environment = installer_env(
        tmp_path,
        {
            'brew': """#!/bin/bash
touch "$FAKE_BREW_MARKER"
""",
        },
    )
    environment['FAKE_BREW_MARKER'] = str(brew_marker)

    result = run_installer('--install-dir', str(install_dir), env=environment)

    assert result.returncode == 1
    assert 'Install directory already exists' in result.stderr
    assert install_dir.is_dir()
    assert not brew_marker.exists()


def test_real_flow_preserves_space_in_install_path(tmp_path: Path):
    install_dir = tmp_path / 'CapsWriter Offline'
    clone_log = tmp_path / 'clone-destination'
    environment = installer_env(
        tmp_path,
        {
            'git': """#!/bin/bash
case "$1" in
    check-ref-format) exit 0 ;;
    clone)
        for argument in "$@"; do destination="$argument"; done
        mkdir -p "$destination/.git"
        printf '%s\\n' "$destination" > "$FAKE_CLONE_LOG"
        ;;
    *) exit 70 ;;
esac
""",
            'uv': """#!/bin/bash
case "$*" in
    'python install 3.12'|'sync --all-groups --frozen') exit 0 ;;
    'run pyinstaller --noconfirm --clean packaging/macos/CapsWriterClient.spec')
        mkdir -p dist/CapsWriter.app
        ;;
    *) exit 71 ;;
esac
""",
            'ffmpeg': '#!/bin/bash\nexit 0\n',
            'codesign': """#!/bin/bash
[[ "$1" == '--verify' && "$2" == '--deep' && "$3" == '--strict' && -d "$4" ]]
""",
        },
    )
    environment['FAKE_CLONE_LOG'] = str(clone_log)

    result = run_installer(
        '--skip-system-deps',
        '--skip-models',
        '--install-dir',
        str(install_dir),
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert clone_log.read_text(encoding='utf-8').strip() == str(install_dir)
    assert (install_dir / 'dist' / 'CapsWriter.app').is_dir()


def test_clone_failure_stops_before_uv_commands(tmp_path: Path):
    install_dir = tmp_path / 'missing-tag'
    uv_marker = tmp_path / 'uv-ran'
    environment = installer_env(
        tmp_path,
        {
            'git': """#!/bin/bash
[[ "$1" == 'check-ref-format' ]] && exit 0
[[ "$1" == 'clone' ]] && exit 42
exit 70
""",
            'uv': """#!/bin/bash
touch "$FAKE_UV_MARKER"
""",
            'ffmpeg': '#!/bin/bash\nexit 0\n',
        },
    )
    environment['FAKE_UV_MARKER'] = str(uv_marker)

    result = run_installer(
        '--skip-system-deps',
        '--skip-models',
        '--skip-build',
        '--install-dir',
        str(install_dir),
        env=environment,
    )

    assert result.returncode == 42
    assert not uv_marker.exists()
    assert not install_dir.exists()
