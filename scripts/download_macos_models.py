#!/usr/bin/env python3
"""Download and verify the default macOS ASR and punctuation models."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelAsset:
    name: str
    url: str
    sha256: str
    install_path: Path
    required_file: Path


ASSETS = (
    ModelAsset(
        name='Paraformer.zip',
        url='https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/Paraformer.zip',
        sha256='a12a3f9791483329441c94ad759cbcf258d7246784a6d368cd3c591add4d888b',
        install_path=Path('models/Paraformer/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx'),
        required_file=Path('model.onnx'),
    ),
    ModelAsset(
        name='Punct-CT-Transformer.zip',
        url='https://github.com/HaujetZhao/CapsWriter-Offline/releases/download/models/Punct-CT-Transformer.zip',
        sha256='de106e6cf13764bd3124f31864bc30158f04961788765b63262bdd5ba21fa421',
        install_path=Path(
            'models/Punct-CT-Transformer/'
            'sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12'
        ),
        required_file=Path('model.onnx'),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'CapsWriter-Offline-macOS-setup'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            member_path = (destination / member.filename).resolve()
            if destination not in member_path.parents and member_path != destination:
                raise ValueError(f'压缩包包含越界路径：{member.filename}')
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f'压缩包包含不允许的符号链接：{member.filename}')
        bundle.extractall(destination)


def install_asset(asset: ModelAsset, project_root: Path, cache_dir: Path, force: bool = False) -> Path:
    install_path = project_root / asset.install_path
    required_file = install_path / asset.required_file
    manifest_path = install_path / '.capswriter-install.json'
    if required_file.is_file() and manifest_path.is_file() and not force:
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            manifest = {}
        if (
            manifest.get('sha256') == asset.sha256
            and manifest.get('required_file_sha256') == sha256_file(required_file)
        ):
            print(f'[已安装] {asset.name}: {install_path}')
            return install_path

    archive = cache_dir / asset.name
    if not archive.is_file() or sha256_file(archive) != asset.sha256:
        archive.unlink(missing_ok=True)
        print(f'[下载] {asset.url}')
        download_file(asset.url, archive)

    actual_hash = sha256_file(archive)
    if actual_hash != asset.sha256:
        raise RuntimeError(f'{asset.name} SHA-256 不匹配：期望 {asset.sha256}，实际 {actual_hash}')
    print(f'[校验通过] {asset.name}: {actual_hash}')

    install_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='capswriter-model-', dir=install_path.parent) as temporary:
        extraction_root = Path(temporary)
        safe_extract(archive, extraction_root)
        extracted_path = extraction_root / install_path.name
        if not (extracted_path / asset.required_file).is_file():
            raise RuntimeError(f'{asset.name} 中缺少 {asset.required_file}')
        if install_path.exists():
            shutil.rmtree(install_path)
        shutil.move(str(extracted_path), install_path)

    manifest = {
        **asdict(asset),
        'install_path': str(asset.install_path),
        'required_file': str(asset.required_file),
        'required_file_sha256': sha256_file(required_file),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'[安装完成] {asset.name}: {install_path}')
    return install_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, help='模型 ZIP 缓存目录')
    parser.add_argument('--force', action='store_true', help='重新校验并安装模型')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = (args.cache_dir or project_root / '.cache' / 'capswriter-models').expanduser().resolve()
    for asset in ASSETS:
        install_asset(asset, project_root, cache_dir, force=args.force)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
