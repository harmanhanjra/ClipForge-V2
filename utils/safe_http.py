"""Constrained HTTPS access for ClipForge's urllib-based media helpers."""

from __future__ import annotations

import inspect
import socket
import urllib.request
from collections.abc import Collection
from urllib.parse import urlparse

_ORIGINAL_URLOPEN = urllib.request.urlopen
_AUDIO_ENGINE_MODULE = "utils.audio_engine"

_POLICIES = {
    "loremflickr.com": ({"loremflickr.com", "www.loremflickr.com"}, {".staticflickr.com"}),
    "mixkit.co": ({"mixkit.co", "www.mixkit.co", "assets.mixkit.co"}, {".mixkit.co"}),
    "pollinations.ai": ({"image.pollinations.ai"}, {".pollinations.ai"}),
}


def _normalize_hosts(hosts: Collection[str]) -> set[str]:
    return {host.rstrip(".").casefold() for host in hosts if host}


def validate_https_url(
    url: str,
    *,
    allowed_hosts: Collection[str],
    allowed_suffixes: Collection[str] = (),
) -> str:
    """Validate an outbound URL against a strict HTTPS hostname allowlist."""
    if not isinstance(url, str) or not url:
        raise ValueError("Outbound URL must be a non-empty string")

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").rstrip(".").casefold()
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Malformed outbound URL") from exc

    if parsed.scheme.casefold() != "https":
        raise ValueError("Only HTTPS outbound URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials in outbound URLs are not allowed")
    if port not in (None, 443):
        raise ValueError("Non-standard HTTPS ports are not allowed")

    normalized_hosts = _normalize_hosts(allowed_hosts)
    normalized_suffixes = tuple(
        suffix.casefold() if suffix.startswith(".") else f".{suffix.casefold()}"
        for suffix in allowed_suffixes
        if suffix
    )
    if host not in normalized_hosts and not any(host.endswith(suffix) for suffix in normalized_suffixes):
        raise ValueError(f"Outbound host is not allowlisted: {host or '<missing>'}")

    return parsed.geturl()


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: Collection[str], allowed_suffixes: Collection[str]):
        super().__init__()
        self.allowed_hosts = tuple(allowed_hosts)
        self.allowed_suffixes = tuple(allowed_suffixes)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_https_url(
            newurl,
            allowed_hosts=self.allowed_hosts,
            allowed_suffixes=self.allowed_suffixes,
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _policy_for_url(url: str) -> tuple[set[str], set[str]]:
    try:
        host = (urlparse(url).hostname or "").rstrip(".").casefold()
    except ValueError as exc:
        raise ValueError("Malformed outbound URL") from exc

    if host in _POLICIES["loremflickr.com"][0]:
        return _POLICIES["loremflickr.com"]
    if host == "mixkit.co" or host.endswith(".mixkit.co"):
        return _POLICIES["mixkit.co"]
    if host == "image.pollinations.ai" or host.endswith(".pollinations.ai"):
        return _POLICIES["pollinations.ai"]
    raise ValueError(
        f"Outbound host is not an approved ClipForge media provider: {host or '<missing>'}"
    )


def _direct_caller_is_audio_engine() -> bool:
    frame = inspect.currentframe()
    try:
        caller = frame.f_back.f_back if frame and frame.f_back else None
        return bool(caller and caller.f_globals.get("__name__") == _AUDIO_ENGINE_MODULE)
    finally:
        del frame


def _guarded_urlopen(
    request,
    data=None,
    timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
    *,
    cafile=None,
    capath=None,
    cadefault=False,
    context=None,
):
    if not _direct_caller_is_audio_engine():
        return _ORIGINAL_URLOPEN(
            request,
            data=data,
            timeout=timeout,
            cafile=cafile,
            capath=capath,
            cadefault=cadefault,
            context=context,
        )

    url = request.full_url if isinstance(request, urllib.request.Request) else request
    allowed_hosts, allowed_suffixes = _policy_for_url(url)
    validate_https_url(
        url,
        allowed_hosts=allowed_hosts,
        allowed_suffixes=allowed_suffixes,
    )
    handlers = [_AllowlistRedirectHandler(allowed_hosts, allowed_suffixes)]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(request, data=data, timeout=timeout)


def install_audio_engine_urlopen_guard() -> None:
    """Install the guard once; non-audio-engine urllib callers remain unchanged."""
    if urllib.request.urlopen is not _guarded_urlopen:
        urllib.request.urlopen = _guarded_urlopen
