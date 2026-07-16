# ClipForge V2

ClipForge is a local-first video creator studio for Windows and the web. It clips permitted YouTube videos, merges uploaded footage, creates voiceovers, generates simple AI videos, and manages finished exports from one interface.

## Features

- YouTube clipping with equal-length or custom timestamp ranges
- Original, vertical (9:16), and horizontal (16:9) output
- Automatic removal of the source soundtrack
- Locally generated ambient audio, licensed-audio upload, or mute output
- Multi-video merging with voiceover and background music
- Neural text-to-speech voices with preview, mood, age, pitch, and speed controls
- NVIDIA NIM transcription and YouTube Shorts metadata generation
- Local export library with playback, search, save, and cleanup controls
- Native Windows application with securely stored NVIDIA credentials

## Requirements

- Python 3.11 or newer
- FFmpeg and FFprobe available on `PATH`
- Microsoft Edge WebView2 for the Windows application
- An NVIDIA API key only when using NVIDIA AI features

## Run locally

```powershell
git clone https://github.com/harmanhanjra/ClipForge-V2.git
cd ClipForge-V2
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5005`.

## Build the Windows application

After completing the local setup:

```powershell
.\windows\build.ps1
```

The portable application is written to `dist\ClipForge.exe`. Build artifacts are intentionally excluded from Git because the executable bundles FFmpeg and is large.

Windows application data is stored in:

- Exports: `%USERPROFILE%\Videos\ClipForge`
- Temporary work files and logs: `%LOCALAPPDATA%\ClipForge`

## NVIDIA AI

Open the **NVIDIA AI** tab and select **Connect securely** to store your key. On Windows, ClipForge encrypts it with DPAPI; the key is never returned to the frontend or written to logs. Use **Test key** to verify the connection.

Alternatively, set `NVIDIA_API_KEY` before starting the application.

## Tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Copyright and platform rules

ClipForge removes the original soundtrack and can synthesize audio without sampled recordings. This does not clear rights to the source video or guarantee that YouTube or another platform will accept or monetize an upload. Only download, edit, and publish media you own or have permission to use, and verify the licence for any uploaded audio.
