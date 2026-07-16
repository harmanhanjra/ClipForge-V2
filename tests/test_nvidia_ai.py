import unittest
from unittest.mock import MagicMock, patch

import app as clipforge_app
from utils.nvidia_ai import (
    NvidiaAIError,
    _parse_json_object,
    _protect,
    _resolve_nvcf_response,
    _unprotect,
    normalize_api_key,
)


class NvidiaAIHelpersTests(unittest.TestCase):
    def test_windows_dpapi_round_trip(self):
        encrypted = _protect("nvapi-test-secret")
        self.assertNotIn("nvapi-test-secret", encrypted)
        self.assertEqual(_unprotect(encrypted), "nvapi-test-secret")

    def test_normalizes_copied_bearer_key(self):
        self.assertEqual(normalize_api_key('  Bearer "nvapi-example"  '), 'nvapi-example')

    @patch("utils.nvidia_ai.requests.get")
    def test_queued_nvcf_response_is_polled(self, get):
        queued = MagicMock(status_code=202, headers={"nvcf-reqid": "request-123"})
        queued.json.return_value = {}
        complete = MagicMock(status_code=200)
        get.return_value = complete
        self.assertIs(_resolve_nvcf_response(queued, "key", 5), complete)
        self.assertIn("request-123", get.call_args.args[0])

    def test_parses_fenced_json(self):
        result = _parse_json_object('```json\n{"title":"A short"}\n```')
        self.assertEqual(result["title"], "A short")

    def test_rejects_non_json_model_output(self):
        with self.assertRaises(NvidiaAIError):
            _parse_json_object("not json")


class NvidiaAIRoutesTests(unittest.TestCase):
    def setUp(self):
        clipforge_app.app.config.update(TESTING=True)
        self.client = clipforge_app.app.test_client()

    @patch.object(clipforge_app, "nvidia_is_configured", return_value=True)
    def test_status_never_returns_key(self, _configured):
        response = self.client.get("/api/nvidia/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"configured": True})
        self.assertNotIn("key", response.get_data(as_text=True).lower())

    @patch.object(clipforge_app, "save_nvidia_api_key")
    def test_connect_saves_without_fragile_models_check(self, save):
        response = self.client.post("/api/nvidia/connect", json={"api_key": "nvapi-test-key-long-enough"})
        self.assertEqual(response.status_code, 200)
        save.assert_called_once()

    @patch.object(clipforge_app, "test_nvidia_connection")
    def test_explicit_verify_endpoint(self, verify):
        response = self.client.post("/api/nvidia/verify")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["verified"])
        verify.assert_called_once()

    @patch.object(clipforge_app, "generate_shorts_metadata")
    def test_metadata_endpoint(self, generate):
        generate.return_value = {
            "title": "Funny GTA moment",
            "description": "Watch to the end.",
            "hashtags": ["#shorts"],
            "hook": "Wait for it",
            "pinned_comment": "What would you do?",
        }
        response = self.client.post(
            "/api/nvidia/generate-metadata",
            json={"transcript": "A funny gaming clip", "language": "English", "tone": "Funny"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["metadata"]["title"], "Funny GTA moment")

    def test_transcribe_blocks_path_traversal(self):
        response = self.client.post("/api/nvidia/transcribe", json={"filename": "../secret.mp4"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
