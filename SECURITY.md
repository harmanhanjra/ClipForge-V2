# Security Notes

ClipForge-V2 is not claimed to be secure or production-ready. This file records security checks, known constraints, and remediation work.

## CI security gates

CI runs the unit test suite, Bandit static analysis for medium/high findings, and `pip-audit` against `requirements.txt`.

## Temporary dependency exception

`PYSEC-2026-2132` for Click is temporarily ignored by `pip-audit` because the current gTTS 2.5.x dependency line requires `click<8.2`, while the advisory is fixed in Click 8.3.3. ClipForge-V2 does not directly import Click and repository search found no use of `click.edit()`, the affected API described by the advisory.

This is a constrained compatibility exception, not a statement that the vulnerable Click version is safe. Remove the exception when gTTS permits a patched Click release, or replace the gTTS fallback with a compatible maintained implementation.

## Open static-analysis findings

Bandit currently reports four medium-severity B310 findings in `utils/audio_engine.py` for `urllib.request.urlopen` calls used by stock-image, Mixkit, and Pollinations fetches. These findings remain blocking in CI until outbound URL handling has explicit HTTPS/domain and redirect validation. They have not been suppressed.

## Reporting

Do not include credentials, API keys, private media, or other sensitive user data in public issue reports.
