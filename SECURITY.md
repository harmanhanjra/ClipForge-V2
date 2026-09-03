# Security Notes

ClipForge-V2 is not claimed to be secure or production-ready. This file records security checks, known constraints, and remediation work.

## CI security gates

CI runs the unit test suite, Bandit static analysis for medium/high findings, and `pip-audit` against `requirements.txt`.

## Temporary dependency exception

`PYSEC-2026-2132` for Click is temporarily ignored by `pip-audit` because the current gTTS 2.5.x dependency line requires `click<8.2`, while the advisory is fixed in Click 8.3.3. ClipForge-V2 does not directly import Click and repository search found no use of `click.edit()`, the affected API described by the advisory.

This is a constrained compatibility exception, not a statement that the vulnerable Click version is safe. Remove the exception when gTTS permits a patched Click release, or replace the gTTS fallback with a compatible maintained implementation.

## Outbound urllib policy

The four `urllib.request.urlopen` call sites in `utils/audio_engine.py` are protected at package initialization by `utils.safe_http`. Calls made directly by the audio engine are restricted to HTTPS, standard port 443, no embedded credentials, and an allowlist for the media providers ClipForge uses: LoremFlickr/Flickr, Mixkit, and Pollinations. Redirect targets are validated against the same provider policy before urllib follows them.

The policy is intentionally scoped to calls originating directly from `utils.audio_engine`; unrelated third-party urllib callers retain their normal behavior. Regression tests reject file/HTTP URLs, localhost and metadata-style IP targets, credential-bearing URLs, non-standard ports, lookalike domains, unknown providers, and cross-domain redirect targets.

Bandit B310 is therefore explicitly skipped in CI after this runtime control and its tests were added. Other medium/high Bandit findings remain blocking. This does not provide a network sandbox, DNS pinning, or complete protection if an allowlisted provider itself is compromised.

## Reporting

Do not include credentials, API keys, private media, or other sensitive user data in public issue reports.
