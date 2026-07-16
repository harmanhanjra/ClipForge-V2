# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil

from PyInstaller.utils.hooks import collect_all, collect_submodules


root = Path(SPECPATH).parent
venv_scripts = root / "venv" / "Scripts"


def resolve_media_binary(name):
    """Resolve Chocolatey shims to the real portable FFmpeg executable."""
    discovered = shutil.which(name)
    if not discovered:
        raise SystemExit(f"Required media binary not found on PATH: {name}")
    source = Path(discovered).resolve()
    # Chocolatey's bin entries are small launcher shims. Copying a shim into a
    # one-file app separates it from Chocolatey's metadata, so it exits with no
    # diagnostic. Bundle the real executable from the package tools directory.
    if source.stat().st_size < 10 * 1024 * 1024 and "chocolatey" in str(source).lower():
        chocolatey_root = source.parent.parent
        real = chocolatey_root / "lib" / "ffmpeg" / "tools" / "ffmpeg" / "bin" / f"{name}.exe"
        if real.exists():
            source = real
    if source.stat().st_size < 10 * 1024 * 1024:
        raise SystemExit(f"Resolved {name} is a launcher shim, not the real media binary: {source}")
    return str(source)


binaries = []
for name in ("ffmpeg.exe", "ffprobe.exe"):
    binaries.append((resolve_media_binary(Path(name).stem), "bin"))

ytdlp = venv_scripts / "yt-dlp.exe"
if not ytdlp.exists():
    raise SystemExit(f"yt-dlp executable not found: {ytdlp}")
binaries.append((str(ytdlp), "bin"))

datas = [(str(root / "static"), "static")]
hiddenimports = collect_submodules("webview")

for package in ("edge_tts", "moviepy", "imageio", "imageio_ffmpeg", "certifi", "curl_cffi", "truststore"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(root / "desktop_app.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ClipForge",
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
    icon=str(root / "windows" / "clipforge.ico"),
)
