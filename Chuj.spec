# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec hry CHUJ (okno bez konzoly, výstup = priečinok dist/Chuj).
#
# Spustenie z PyCharmu (Run > Edit Configurations > + Python):
#   Module name:       PyInstaller
#   Parameters:        --noconfirm --clean Chuj.spec
#   Working directory: koreň projektu (C:\Chuj)
# alebo z terminálu v PyCharme:
#   python -m PyInstaller --noconfirm --clean Chuj.spec
#
# Všetky cesty sa odvodzujú od SPECPATH (priečinok tohto súboru), takže
# build funguje aj keď sa spustí z iného pracovného priečinka.
# Hra číta assety relatívne k aktuálnemu priečinku ("assets/..."), preto
# sa priečinok assets pribaľuje celý (aj pozadia stola table*.jpg, ktoré si
# hráč volí v Nastaveniach). Hráčske dáta (profil, nastavenia, uložená
# hra, logy) sa ukladajú do Documents/Chuj, nie do priečinka s hrou.

import os
import sys

ROOT = SPECPATH
ICON = os.path.join(ROOT, 'assets', 'graphics', 'chuj.ico')

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, 'assets'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Nepotrebné časti štandardnej knižnice a balíčkov — hra používa len
    # pygame. (numpy, tkinter a pod. by sa inak mohli pritiahnuť z prostredia.)
    excludes=[
        'tkinter', 'unittest', 'pydoc', 'doctest', 'lib2to3',
        'distutils', 'setuptools', 'pkg_resources', 'numpy',
        'tester',          # testovacie nástroje nepatria do hry
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Chuj',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX zámerne vypnutý: kompresia SDL/pygame knižníc občas rozbije
    # spustenie a zvyšuje počet falošných poplachov antivírusov.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON] if sys.platform == 'win32' and os.path.exists(ICON) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Chuj',
)
