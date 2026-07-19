# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).parents[1]
hidden_imports = collect_submodules('core.client') + collect_submodules('core.tools')

a = Analysis(
    [str(project_root / 'start_client.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / 'build_hook.py')],
    excludes=['core.server'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CapsWriter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CapsWriter',
)

app = BUNDLE(
    collection,
    name='CapsWriter.app',
    icon=str(project_root / 'assets' / 'icon.ico'),
    bundle_identifier='io.github.alex-ghost599.capswriter-offline.client',
    info_plist={
        'CFBundleDisplayName': 'CapsWriter',
        'NSHighResolutionCapable': True,
        'NSMicrophoneUsageDescription': 'CapsWriter 需要使用麦克风进行离线语音转文字。',
    },
)
