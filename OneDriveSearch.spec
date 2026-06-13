# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\tcl86t.dll', '.'), ('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\tk86t.dll', '.'), ('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\libcrypto-1_1-x64.dll', '.'), ('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\libssl-1_1-x64.dll', '.'), ('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\liblzma.dll', '.'), ('C:\\Users\\ryanf\\anaconda3\\Library\\bin\\libbz2.dll', '.')],
    datas=[('C:\\Users\\ryanf\\anaconda3\\Library\\lib\\tcl8.6', 'tcl8.6'), ('C:\\Users\\ryanf\\anaconda3\\Library\\lib\\tk8.6', 'tk8.6')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OneDriveSearch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OneDriveSearch',
)
