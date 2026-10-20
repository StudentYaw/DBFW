# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Tesseract-Pfad
TESSERACT_DIR = r'C:\Program Files\Tesseract-OCR'

# Alle Tesseract .dll und tesseract.exe sammeln
tesseract_binaries = []
for fname in os.listdir(TESSERACT_DIR):
    fpath = os.path.join(TESSERACT_DIR, fname)
    if os.path.isfile(fpath) and (fname.endswith('.dll') or fname == 'tesseract.exe'):
        tesseract_binaries.append((fpath, 'tesseract-ocr'))

# tessdata (nur eng + osd + pdf.ttf)
tessdata_files = [
    (os.path.join(TESSERACT_DIR, 'tessdata', 'eng.traineddata'), 'tesseract-ocr/tessdata'),
    (os.path.join(TESSERACT_DIR, 'tessdata', 'osd.traineddata'), 'tesseract-ocr/tessdata'),
    (os.path.join(TESSERACT_DIR, 'tessdata', 'pdf.ttf'),         'tesseract-ocr/tessdata'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=tesseract_binaries,
    datas=[
        ('res', 'res'),
        ('config.yaml', '.'),
    ] + tessdata_files,
    hiddenimports=[
        'pytesseract',
        'PIL._imaging',
        'PIL.Image',
        'PIL.ImageGrab',
        'pyautogui',
        'pygetwindow',
        'cv2',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DBFW',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='res/logo.ico',
    onefile=True,
)
