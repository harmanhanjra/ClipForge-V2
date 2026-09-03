"""ClipForge utility package security initialization."""

from .safe_http import install_audio_engine_urlopen_guard

install_audio_engine_urlopen_guard()
