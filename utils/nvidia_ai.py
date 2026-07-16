"""NVIDIA NIM helpers for ClipForge.

The user's API key is encrypted with Windows DPAPI before it is persisted.
Network calls live in this module so Flask routes never log credentials or
expose a saved key back to the browser UI.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

# Use the Windows certificate store. This is essential on PCs where antivirus,
# a company proxy, or the ISP installs a trusted local HTTPS issuer that is not
# present in Requests' bundled certifi file.
if os.name == "nt":
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

import requests


LLM_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
ASR_ENDPOINT = (
    "https://1598d209-5e27-4d3c-8079-4751568b1081."
    "invocation.api.nvcf.nvidia.com/v1/audio/transcriptions"
)
DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"
NVCF_STATUS_ENDPOINT = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/{request_id}"


class NvidiaAIError(RuntimeError):
    """A safe, user-facing NVIDIA integration error."""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _settings_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    folder = root / "ClipForge"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "nvidia.json"


def _protect(value: str) -> str:
    if os.name != "nt":
        raise NvidiaAIError("Secure key storage is available in the Windows app only.")
    raw = value.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    source = _DataBlob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "ClipForge NVIDIA API key", None, None, None, 0,
        ctypes.byref(target),
    )
    if not ok:
        raise NvidiaAIError("Windows could not encrypt the NVIDIA API key.")
    try:
        return base64.b64encode(ctypes.string_at(target.pbData, target.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def _unprotect(value: str) -> str:
    if os.name != "nt":
        return ""
    raw = base64.b64decode(value)
    buffer = ctypes.create_string_buffer(raw)
    source = _DataBlob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)
    )
    if not ok:
        return ""
    try:
        return ctypes.string_at(target.pbData, target.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def normalize_api_key(api_key: str) -> str:
    """Accept copied keys, including an accidental ``Bearer `` prefix."""
    key = api_key.strip().strip('"').strip("'").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip().strip('"').strip("'").strip()
    return key


def save_api_key(api_key: str) -> None:
    key = normalize_api_key(api_key)
    if not key:
        raise NvidiaAIError("Enter your NVIDIA API key first.")
    if len(key) < 20:
        raise NvidiaAIError("That NVIDIA API key appears incomplete.")
    payload = {"encrypted_api_key": _protect(key)}
    _settings_path().write_text(json.dumps(payload), encoding="utf-8")


def clear_api_key() -> None:
    path = _settings_path()
    if path.exists():
        path.unlink()


def get_api_key() -> str:
    environment_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if environment_key:
        return environment_key
    try:
        payload = json.loads(_settings_path().read_text(encoding="utf-8"))
        return _unprotect(payload.get("encrypted_api_key", ""))
    except (OSError, ValueError, TypeError):
        return ""


def is_configured() -> bool:
    return bool(get_api_key())


def _safe_error(response: requests.Response) -> str:
    if response.status_code in (401, 403):
        return "NVIDIA rejected the API key. Check the key and reconnect."
    if response.status_code == 429:
        return "NVIDIA rate limit or credits limit reached. Try again later."
    try:
        data = response.json()
        detail = data.get("detail") or data.get("error") or data.get("message")
        if isinstance(detail, dict):
            detail = detail.get("message")
        if detail:
            return f"NVIDIA API error: {str(detail)[:300]}"
    except ValueError:
        pass
    return f"NVIDIA API request failed (HTTP {response.status_code})."


def _resolve_nvcf_response(
    response: requests.Response,
    key: str,
    max_wait_seconds: int = 300,
) -> requests.Response:
    """Poll NVIDIA Cloud Functions when an invocation is queued (HTTP 202)."""
    if response.status_code != 202:
        return response
    try:
        initial = response.json()
    except ValueError:
        initial = {}
    request_id = (
        response.headers.get("nvcf-reqid")
        or initial.get("requestId")
        or initial.get("reqId")
    )
    if not request_id:
        raise NvidiaAIError("NVIDIA queued the request but returned no tracking ID.")

    deadline = time.monotonic() + max_wait_seconds
    headers = {"Authorization": f"Bearer {key}", "NVCF-POLL-SECONDS": "10"}
    status_url = NVCF_STATUS_ENDPOINT.format(request_id=request_id)
    while time.monotonic() < deadline:
        try:
            polled = requests.get(status_url, headers=headers, timeout=20, allow_redirects=True)
        except requests.RequestException as exc:
            raise NvidiaAIError("NVIDIA stopped responding while processing the request.") from exc
        if polled.status_code != 202:
            return polled
        time.sleep(2)
    raise NvidiaAIError("NVIDIA processing timed out. Please try again.")


def test_connection(api_key: str | None = None) -> None:
    key = normalize_api_key(api_key or get_api_key())
    if not key:
        raise NvidiaAIError("NVIDIA API key is not connected.")
    try:
        response = requests.post(
            LLM_ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "Reply OK"}],
                "max_tokens": 2,
                "temperature": 0,
                "stream": False,
            },
            timeout=35,
        )
    except requests.exceptions.SSLError as exc:
        raise NvidiaAIError("Secure connection to NVIDIA failed. Windows certificates need attention.") from exc
    except requests.RequestException as exc:
        raise NvidiaAIError("Could not reach NVIDIA. Check your internet connection.") from exc
    response = _resolve_nvcf_response(response, key, max_wait_seconds=45)
    if not response.ok:
        raise NvidiaAIError(_safe_error(response))


def transcribe_video(video_path: str, language: str = "en-US") -> str:
    key = get_api_key()
    if not key:
        raise NvidiaAIError("Connect your NVIDIA API key first.")

    source = Path(video_path)
    if not source.is_file():
        raise NvidiaAIError("The selected video could not be found.")

    fd, audio_path = tempfile.mkstemp(prefix="clipforge_asr_", suffix=".flac")
    os.close(fd)
    try:
        command = [
            "ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "flac", "-compression_level", "8", audio_path,
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if result.returncode != 0 or not os.path.exists(audio_path):
            raise NvidiaAIError("Could not extract audio from the selected video.")
        if os.path.getsize(audio_path) > 25 * 1024 * 1024:
            raise NvidiaAIError("This clip is too long for one transcription request. Use a shorter clip.")

        try:
            with open(audio_path, "rb") as audio:
                response = requests.post(
                    ASR_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "NVCF-POLL-SECONDS": "30",
                    },
                    data={"language": language, "response_format": "json"},
                    files={"file": (source.stem + ".flac", audio, "audio/flac")},
                    timeout=300,
                )
        except requests.exceptions.SSLError as exc:
            raise NvidiaAIError("Secure connection to NVIDIA failed. Windows certificates need attention.") from exc
        except requests.RequestException as exc:
            raise NvidiaAIError("Could not reach NVIDIA transcription service.") from exc
        response = _resolve_nvcf_response(response, key, max_wait_seconds=300)
        if not response.ok:
            raise NvidiaAIError(_safe_error(response))
        try:
            text = response.json().get("text", "").strip()
        except ValueError:
            text = response.text.strip()
        if not text:
            raise NvidiaAIError("NVIDIA returned an empty transcript for this clip.")
        return text
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


def _parse_json_object(content: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise NvidiaAIError("NVIDIA returned an unexpected metadata format.")
        try:
            result = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise NvidiaAIError("NVIDIA returned an unexpected metadata format.") from exc
    if not isinstance(result, dict):
        raise NvidiaAIError("NVIDIA returned an unexpected metadata format.")
    return result


def generate_shorts_metadata(
    transcript: str,
    language: str = "English",
    tone: str = "High-energy",
    model: str = DEFAULT_MODEL,
) -> dict:
    key = get_api_key()
    if not key:
        raise NvidiaAIError("Connect your NVIDIA API key first.")
    source = transcript.strip()
    if not source:
        raise NvidiaAIError("Add a transcript or topic first.")

    prompt = f"""Create accurate YouTube Shorts metadata from the source below.
Language: {language}
Tone: {tone}
Never invent facts that are not supported by the source. Make the title compelling
without misleading clickbait. Keep the title under 70 characters. Write a useful
description with a natural call to action. Return ONLY valid JSON with exactly these
keys: title (string), description (string), hashtags (array of 5 to 10 strings),
hook (string), pinned_comment (string).

SOURCE:
{source[:14000]}"""
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert, truthful YouTube Shorts editor."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.65,
        "top_p": 0.9,
        "max_tokens": 900,
        "stream": False,
    }
    try:
        response = requests.post(
            LLM_ENDPOINT,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "NVCF-POLL-SECONDS": "30",
            },
            json=payload,
            timeout=120,
        )
    except requests.exceptions.SSLError as exc:
        raise NvidiaAIError("Secure connection to NVIDIA failed. Windows certificates need attention.") from exc
    except requests.RequestException as exc:
        raise NvidiaAIError("Could not reach NVIDIA metadata service.") from exc
    response = _resolve_nvcf_response(response, key, max_wait_seconds=180)
    if not response.ok:
        raise NvidiaAIError(_safe_error(response))
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise NvidiaAIError("NVIDIA returned an unexpected response.") from exc
    result = _parse_json_object(content)
    hashtags = result.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    result["hashtags"] = [str(tag).strip() for tag in hashtags if str(tag).strip()][:10]
    for field in ("title", "description", "hook", "pinned_comment"):
        result[field] = str(result.get(field, "")).strip()
    return result
