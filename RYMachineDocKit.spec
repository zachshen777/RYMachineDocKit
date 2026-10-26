# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：pyinstaller RYMachineDocKit.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/resources', 'resources')],
    hiddenimports=['app.modules.pdf_extract', 'app.modules.pdf_edit',
                   'app.modules.file_classify', 'app.modules.batch_rename'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RYMachineDocKit',
    icon=None,
    console=False,
    disable_windowed_traceback=False,
)
