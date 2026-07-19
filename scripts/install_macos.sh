#!/usr/bin/env bash

set -Eeuo pipefail

readonly REPO_URL='https://github.com/Alex-ghost599/CapsWriter-Offline-macOS.git'
readonly DEFAULT_REF='v2.6.0-macos.1'

INSTALL_DIR="${HOME}/CapsWriter-Offline-macOS"
REF="${DEFAULT_REF}"
SKIP_MODELS=0
SKIP_BUILD=0
SKIP_SYSTEM_DEPS=0
DRY_RUN=0

usage() {
    cat <<'EOF'
Install CapsWriter-Offline-macOS from source on Apple Silicon.

Usage:
  bash install-macos.sh [options]

Options:
  --install-dir PATH    Install directory (default: ~/CapsWriter-Offline-macOS)
  --ref REF             Git tag or branch to install (default: v2.6.0-macos.1)
  --skip-models         Skip the verified ASR and punctuation model download
  --skip-build          Skip building dist/CapsWriter.app
  --skip-system-deps    Do not run Homebrew; require uv and ffmpeg in PATH
  --dry-run             Print commands without changing the system
  -h, --help            Show this help

The installer never resets an existing checkout and never starts the app.
The install directory must not already exist.
EOF
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

handle_error() {
    local line="$1"
    local status="$2"
    printf '\nInstallation stopped at line %s (exit %s).\n' "$line" "$status" >&2
    exit "$status"
}

trap 'handle_error "$LINENO" "$?"' ERR

print_command() {
    printf '  $'
    printf ' %q' "$@"
    printf '\n'
}

run() {
    print_command "$@"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        "$@"
    fi
}

run_in_dir() {
    local directory="$1"
    shift
    printf '  $ cd %q &&' "$directory"
    printf ' %q' "$@"
    printf '\n'
    if [[ "$DRY_RUN" -eq 0 ]]; then
        (
            cd "$directory"
            "$@"
        )
    fi
}

require_command() {
    local command_name="$1"
    local help_text="$2"
    command -v "$command_name" >/dev/null 2>&1 || die "$help_text"
}

take_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "$value" ]] || die "$option requires a value."
    [[ "$value" != -* ]] || die "$option requires a value, not another option."
    printf '%s' "$value"
}

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --install-dir)
            INSTALL_DIR="$(take_value "$1" "${2:-}")"
            shift 2
            ;;
        --ref)
            REF="$(take_value "$1" "${2:-}")"
            shift 2
            ;;
        --skip-models)
            SKIP_MODELS=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        --skip-system-deps)
            SKIP_SYSTEM_DEPS=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            [[ "$#" -eq 0 ]] || die 'Positional arguments are not supported.'
            ;;
        *)
            printf 'Unknown option: %s\n\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$INSTALL_DIR" == \~ ]]; then
    INSTALL_DIR="$HOME"
elif [[ "$INSTALL_DIR" == \~/* ]]; then
    INSTALL_DIR="${HOME}/${INSTALL_DIR:2}"
fi

[[ "$(uname -s)" == 'Darwin' ]] || die 'This installer supports macOS only.'
[[ "$(uname -m)" == 'arm64' ]] || die 'This release supports Apple Silicon (arm64) only.'

printf 'CapsWriter-Offline-macOS source installer\n'
printf '  Repository: %s\n' "$REPO_URL"
printf '  Ref:        %s\n' "$REF"
printf '  Directory:  %s\n\n' "$INSTALL_DIR"

if [[ "$DRY_RUN" -eq 0 ]]; then
    require_command git 'Git is required. Run xcode-select --install, then retry.'
    git check-ref-format --branch "$REF" >/dev/null 2>&1 || die "Invalid Git ref: $REF"
fi

if [[ -e "$INSTALL_DIR" || -L "$INSTALL_DIR" ]]; then
    die "Install directory already exists; choose a fresh --install-dir: $INSTALL_DIR"
fi

if [[ "$SKIP_SYSTEM_DEPS" -eq 0 ]]; then
    if [[ "$DRY_RUN" -eq 0 ]] && ! command -v brew >/dev/null 2>&1; then
        die 'Homebrew is required. Install it from https://brew.sh, then retry.'
    fi
    run env HOMEBREW_NO_AUTO_UPDATE=1 brew install uv ffmpeg
elif [[ "$DRY_RUN" -eq 0 ]]; then
    require_command uv 'uv is required in PATH when --skip-system-deps is used.'
    require_command ffmpeg 'ffmpeg is required in PATH when --skip-system-deps is used.'
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
    require_command uv 'uv installation failed or uv is not in PATH.'
    require_command ffmpeg 'ffmpeg installation failed or ffmpeg is not in PATH.'
fi

run mkdir -p "$(dirname "$INSTALL_DIR")"
run git clone --depth 1 --single-branch --branch "$REF" "$REPO_URL" "$INSTALL_DIR"

run_in_dir "$INSTALL_DIR" uv python install 3.12
run_in_dir "$INSTALL_DIR" uv sync --all-groups --frozen

if [[ "$SKIP_MODELS" -eq 0 ]]; then
    run_in_dir "$INSTALL_DIR" uv run python scripts/download_macos_models.py
else
    printf '\nSkipping model download. Run this later:\n'
    printf '  cd %q && uv run python scripts/download_macos_models.py\n' "$INSTALL_DIR"
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
    run_in_dir "$INSTALL_DIR" uv run pyinstaller --noconfirm --clean packaging/macos/CapsWriterClient.spec
    if [[ "$DRY_RUN" -eq 0 ]]; then
        [[ -d "$INSTALL_DIR/dist/CapsWriter.app" ]] || die 'Client build did not produce dist/CapsWriter.app.'
        run codesign --verify --deep --strict "$INSTALL_DIR/dist/CapsWriter.app"
    fi
else
    printf '\nSkipping client build. Run this later:\n'
    printf '  cd %q && uv run pyinstaller --noconfirm --clean packaging/macos/CapsWriterClient.spec\n' "$INSTALL_DIR"
fi

printf '\nInstallation steps completed. The installer did not start any process.\n'
printf 'Start the local server in one Terminal window:\n'
printf '  cd %q && CAPSWRITER_MODEL_TYPE=paraformer uv run python start_server.py\n' "$INSTALL_DIR"
if [[ "$SKIP_BUILD" -eq 0 ]]; then
    printf 'Then start the client:\n'
    printf '  open %q\n' "$INSTALL_DIR/dist/CapsWriter.app"
fi
printf 'On each Mac, grant Microphone, Accessibility, and Input Monitoring permissions to CapsWriter.\n'
