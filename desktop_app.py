"""Native Windows launcher for ClipForge.

The Flask application runs only on a random loopback port and is displayed in
an Edge WebView2 desktop window. User exports live outside the application
bundle so they survive upgrades and one-file extraction cleanup.
"""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
from pathlib import Path


APP_NAME = "ClipForge"
WINDOW_TITLE = "ClipForge — Video Creator Studio"
_LOG_STREAM = None


def _known_folder(csidl: int, fallback: Path) -> Path:
    """Return a Windows known folder without adding a platform dependency."""
    buffer = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer)
    return Path(buffer.value) if result == 0 and buffer.value else fallback


def configure_runtime() -> tuple[Path, Path]:
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    videos_dir = _known_folder(14, home / "Videos")  # CSIDL_MYVIDEO

    upload_dir = local_app_data / APP_NAME / "work"
    output_dir = videos_dir / APP_NAME
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Windowed executables otherwise discard Python/FFmpeg diagnostics. Keep a
    # bounded local log so failed commands can be diagnosed instead of looking
    # as if they silently stopped.
    global _LOG_STREAM
    log_path = local_app_data / APP_NAME / "clipforge.log"
    if log_path.exists() and log_path.stat().st_size > 5 * 1024 * 1024:
        log_path.write_text("", encoding="utf-8")
    _LOG_STREAM = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _LOG_STREAM
    sys.stderr = _LOG_STREAM
    os.environ["CLIPFORGE_LOG_FILE"] = str(log_path)

    os.environ["CLIPFORGE_UPLOAD_DIR"] = str(upload_dir)
    os.environ["CLIPFORGE_OUTPUT_DIR"] = str(output_dir)

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_bin = bundle_root / "bin"
    if bundled_bin.is_dir():
        os.environ["PATH"] = f"{bundled_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    return upload_dir, output_dir


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    configure_runtime()

    from waitress import create_server
    import webview
    from app import app

    logging.getLogger("waitress").setLevel(logging.ERROR)
    port = available_port()
    server = create_server(app, host="127.0.0.1", port=port, threads=8)
    server_thread = threading.Thread(target=server.run, name="clipforge-server", daemon=True)
    server_thread.start()

    window = webview.create_window(
        WINDOW_TITLE,
        url=f"http://127.0.0.1:{port}",
        width=1440,
        height=920,
        min_size=(980, 680),
        background_color="#080A0F",
        text_select=False,
    )

    try:
        webview.start(gui="edgechromium", debug=False, private_mode=False)
    finally:
        server.close()


if __name__ == "__main__":
    main()
