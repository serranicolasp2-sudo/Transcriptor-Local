# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Localizar carpeta site-packages
site_pkg = Path(sys.prefix) / 'Lib' / 'site-packages'
if not site_pkg.exists():
    site_pkg = Path(SPECPATH) / 'entorno' / 'Lib' / 'site-packages'

# Recolectar datos de paquetes clave
datas = []
for pkg in ['customtkinter', 'pyannote.audio', 'pyannote.core', 'pyannote.pipeline', 'pyannote.database', 'faster_whisper', 'lightning', 'pytorch_lightning', 'torch', 'torchaudio']:
    try:
        datas.extend(collect_data_files(pkg))
    except Exception:
        pass

# Recolectar exhaustivamente todos los submódulos de paquetes con imports dinámicos mediante recorrido del sistema de archivos
packages_to_scan = [
    'pyannote',
    'asteroid_filterbanks',
    'torch_audiomentations',
    'pytorch_metric_learning',
    'lightning',
    'pytorch_lightning',
    'torchmetrics',
    'faster_whisper',
    'customtkinter',
    'docx',
    'soundfile',
    'ctranslate2',
    'huggingface_hub',
]

hidden_imports = [
    'unittest',
    'scipy',
    'scipy.signal',
    'scipy.special',
    'sklearn',
    'psutil',
    'pydub',
    'tqdm',
    'src',
    'src.config',
    'src.engine',
    'src.exporter',
    'src.player',
    'src.gui',
    'src.acelerador',
]

for pkg in packages_to_scan:
    pkg_dir = site_pkg / pkg
    if pkg_dir.exists():
        for root, dirs, files in os.walk(pkg_dir):
            for f in files:
                if f.endswith('.py'):
                    rel = Path(root).relative_to(site_pkg)
                    mod_parts = list(rel.parts)
                    if f != '__init__.py':
                        mod_parts.append(f[:-3])
                    mod_name = '.'.join(mod_parts)
                    hidden_imports.append(mod_name)

hidden_imports = sorted(list(set(hidden_imports)))

# Tema visual e ícono (src/tema.py los busca en sys._MEIPASS/recursos)
datas.append(('recursos/tema_tutiendita.json', 'recursos'))
datas.append(('recursos/transcriptor.ico', 'recursos'))
datas.append(('recursos/transcriptor_256.png', 'recursos'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Modo carpeta (onedir): arranca rápido y es lo que empaqueta el instalador (instalador\Transcriptor.iss)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Transcriptor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='recursos/transcriptor.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Transcriptor',
)
