import stat
import zipfile
from pathlib import Path

import pytest

from scripts.download_macos_models import ModelAsset, install_asset, safe_extract, sha256_file


def test_sha256_file(tmp_path: Path):
    payload = tmp_path / 'payload.bin'
    payload.write_bytes(b'CapsWriter')

    assert sha256_file(payload) == '10dcf187888763f7ecf61f11c750b7e5f0d4f693c0125109714915eed6bd4949'


def test_safe_extract_rejects_parent_traversal(tmp_path: Path):
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('../escape.txt', 'blocked')

    with pytest.raises(ValueError, match='越界路径'):
        safe_extract(archive, tmp_path / 'output')


def test_safe_extract_rejects_symbolic_link(tmp_path: Path):
    archive = tmp_path / 'unsafe-link.zip'
    link = zipfile.ZipInfo('model/link')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(link, '../outside')

    with pytest.raises(ValueError, match='符号链接'):
        safe_extract(archive, tmp_path / 'output')


def test_install_repairs_corrupted_required_file(tmp_path: Path):
    project_root = tmp_path / 'project'
    cache_dir = tmp_path / 'cache'
    archive = cache_dir / 'TestModel.zip'
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('test-model/model.onnx', b'valid-model')

    asset = ModelAsset(
        name=archive.name,
        url='https://invalid.example/TestModel.zip',
        sha256=sha256_file(archive),
        install_path=Path('models/test-model'),
        required_file=Path('model.onnx'),
    )
    install_path = install_asset(asset, project_root, cache_dir)
    (install_path / 'model.onnx').write_bytes(b'corrupted')

    install_asset(asset, project_root, cache_dir)

    assert (install_path / 'model.onnx').read_bytes() == b'valid-model'
