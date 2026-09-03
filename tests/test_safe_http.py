import unittest
import urllib.request

import utils
from utils import safe_http


class SafeHttpTests(unittest.TestCase):
    def test_guard_is_installed_for_utils_package(self):
        self.assertIs(urllib.request.urlopen, safe_http._guarded_urlopen)

    def test_accepts_exact_and_subdomain_allowlists(self):
        self.assertEqual(
            safe_http.validate_https_url(
                "https://mixkit.co/video",
                allowed_hosts={"mixkit.co"},
            ),
            "https://mixkit.co/video",
        )
        self.assertEqual(
            safe_http.validate_https_url(
                "https://assets.mixkit.co/video.mp4",
                allowed_hosts={"mixkit.co"},
                allowed_suffixes={".mixkit.co"},
            ),
            "https://assets.mixkit.co/video.mp4",
        )

    def test_rejects_scheme_credentials_port_and_unlisted_hosts(self):
        cases = (
            "http://mixkit.co/video",
            "file:///etc/passwd",
            "https://user:pass@mixkit.co/video",
            "https://mixkit.co:444/video",
            "https://127.0.0.1/internal",
            "https://169.254.169.254/latest/meta-data/",
            "https://evilmixkit.co/video",
        )
        for url in cases:
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_http.validate_https_url(
                    url,
                    allowed_hosts={"mixkit.co"},
                    allowed_suffixes={".mixkit.co"},
                )

    def test_unknown_media_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_http._policy_for_url("https://example.com/video.mp4")

    def test_redirect_handler_rejects_cross_domain_redirect(self):
        handler = safe_http._AllowlistRedirectHandler(
            {"mixkit.co"},
            {".mixkit.co"},
        )
        request = urllib.request.Request("https://mixkit.co/video")
        with self.assertRaises(ValueError):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://127.0.0.1/internal",
            )

    def test_direct_audio_engine_call_rejects_unapproved_url_before_network(self):
        namespace = {
            "__name__": "utils.audio_engine",
            "urllib": __import__("urllib"),
        }
        with self.assertRaises(ValueError):
            exec(
                "urllib.request.urlopen('https://127.0.0.1/internal', timeout=1)",
                namespace,
            )


if __name__ == "__main__":
    unittest.main()
