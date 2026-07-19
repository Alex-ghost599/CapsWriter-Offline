from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_macos.sh"
AGENT_GUIDE = ROOT / "docs" / "agent-macos-install.md"
MACOS_SETUP = ROOT / "docs" / "macos-setup.md"
README = ROOT / "readme.md"

RELEASE = "v2.6.0-macos.2"
COMMIT = "040e6ffc22ab214367a8ce1e834195ac4f95639d"
INSTALLER_SHA256 = "b8d6f8fc861ae64c46a10e0cd9b224a18fe39323a6d4ba29673995cdf2e57b77"
GUIDE_URL = (
    "https://github.com/Alex-ghost599/CapsWriter-Offline-macOS/"
    "blob/develop/docs/agent-macos-install.md"
)


def test_agent_guide_locks_the_release_and_installer_hash():
    installer_text = INSTALLER.read_text(encoding="utf-8")
    guide_text = AGENT_GUIDE.read_text(encoding="utf-8")

    assert f"readonly DEFAULT_REF='{RELEASE}'" in installer_text
    assert sha256(INSTALLER.read_bytes()).hexdigest() == INSTALLER_SHA256
    assert RELEASE in guide_text
    assert COMMIT in guide_text
    assert INSTALLER_SHA256 in guide_text


def test_readme_includes_agent_guide_prompt_and_release_hash():
    readme_text = README.read_text(encoding="utf-8")

    assert GUIDE_URL in readme_text
    assert INSTALLER_SHA256 in readme_text
    assert "请先完整阅读这份安装执行规约" in readme_text
    assert "真人右 Shift 录音" in readme_text


def test_macos_start_commands_explicitly_bind_to_loopback():
    for path in (README, AGENT_GUIDE, MACOS_SETUP):
        contents = path.read_text(encoding="utf-8")
        assert "CAPSWRITER_SERVER_BIND=127.0.0.1" in contents
        assert "CAPSWRITER_SERVER_PORT=6016" in contents


def test_public_install_docs_do_not_embed_user_home_paths():
    public_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (README, AGENT_GUIDE, MACOS_SETUP)
    )

    assert "/Users/" not in public_docs
