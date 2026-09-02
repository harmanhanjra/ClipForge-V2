import io
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import app as clipforge_app


class FeatureRouteSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.uploads = os.path.join(self.temp.name, "uploads")
        self.outputs = os.path.join(self.temp.name, "outputs")
        os.makedirs(self.uploads)
        os.makedirs(self.outputs)
        self.old_uploads = clipforge_app.UPLOAD_FOLDER
        self.old_outputs = clipforge_app.OUTPUT_FOLDER
        clipforge_app.UPLOAD_FOLDER = self.uploads
        clipforge_app.OUTPUT_FOLDER = self.outputs
        clipforge_app.app.config.update(TESTING=True)
        self.client = clipforge_app.app.test_client()

    def tearDown(self):
        clipforge_app.UPLOAD_FOLDER = self.old_uploads
        clipforge_app.OUTPUT_FOLDER = self.old_outputs
        self.temp.cleanup()

    def test_shell_voices_library_and_download(self):
        with open(os.path.join(self.outputs, "ready.mp4"), "wb") as handle:
            handle.write(b"video")
        self.assertEqual(self.client.get("/").status_code, 200)
        voices = self.client.get("/api/voices")
        self.assertEqual(voices.status_code, 200)
        self.assertIn("voices", voices.get_json())
        library = self.client.get("/api/outputs").get_json()
        self.assertEqual(library[0]["filename"], "ready.mp4")
        self.assertEqual(self.client.get("/api/outputs/ready.mp4").status_code, 200)

    @patch.object(clipforge_app, "generate_preview")
    def test_voice_preview(self, preview):
        def make_preview(**kwargs):
            with open(kwargs["output_path"], "wb") as handle:
                handle.write(b"ID3-preview")
            return True
        preview.side_effect = make_preview
        response = self.client.post("/api/preview-voice", data={"voice": "test", "lang": "en-US"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")

    @patch.object(clipforge_app, "concatenate_clips")
    def test_video_merge_without_audio(self, concatenate):
        def create_merge(_paths, aspect_ratio, output_path):
            with open(output_path, "wb") as handle:
                handle.write(b"merged-video")
            return 2.0
        concatenate.side_effect = create_merge
        response = self.client.post(
            "/api/merge",
            data={
                "videos": (io.BytesIO(b"input-video"), "input.mp4"),
                "audio_source": "none",
                "aspect_ratio": "vertical",
            },
            content_type="multipart/form-data",
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertTrue(os.path.exists(os.path.join(self.outputs, data["filename"])))

    @patch.object(clipforge_app, "apply_copyright_filters")
    @patch.object(clipforge_app, "slice_video")
    @patch.object(clipforge_app.subprocess, "run")
    def test_youtube_clipper_pipeline(self, run, slice_video, apply_filters):
        def fake_run(command, **_kwargs):
            output = command[command.index("-o") + 1]
            with open(output, "wb") as handle:
                handle.write(b"downloaded-video")
            return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

        def fake_slice(_source, output_dir, **_kwargs):
            sliced = os.path.join(output_dir, "clip_1.mp4")
            with open(sliced, "wb") as handle:
                handle.write(b"slice")
            return [sliced]

        def fake_filter(source, target, _filters):
            shutil.copyfile(source, target)

        run.side_effect = fake_run
        slice_video.side_effect = fake_slice
        apply_filters.side_effect = fake_filter
        response = self.client.post(
            "/api/clip",
            data={
                "url": "https://www.youtube.com/watch?v=test",
                "mode": "auto",
                "interval": "30",
                "audio_mode": "upload",
                "replacement_audio": (io.BytesIO(b"licensed-audio"), "music.mp3"),
            },
            content_type="multipart/form-data",
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["filenames"]), 1)
        options = apply_filters.call_args.args[2]
        self.assertEqual(options["audio_mode"], "upload")
        self.assertTrue(options["replacement_audio_path"].endswith(".mp3"))

    def test_rejects_non_youtube_download_url(self):
        response = self.client.post(
            "/api/clip",
            data={"url": "https://example.com/video.mp4", "mode": "auto"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only HTTPS YouTube URLs", response.get_json()["error"])

    @patch.object(clipforge_app, "concatenate_clips")
    def test_rejects_unsupported_video_upload(self, concatenate):
        response = self.client.post(
            "/api/merge",
            data={"videos": (io.BytesIO(b"not-video"), "payload.exe")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported video type", response.get_json()["error"])
        concatenate.assert_not_called()

    @patch.object(clipforge_app, "generate_ai_video")
    def test_ai_video_creator(self, generate):
        generate.return_value = {"success": True, "duration": 3.0, "sentences_count": 1}
        response = self.client.post(
            "/api/generate-video",
            data={"script_text": "A complete test sentence.", "theme": "auto"},
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["slides"], 1)

    @patch.object(clipforge_app, "save_nvidia_api_key")
    @patch.object(clipforge_app, "transcribe_video", return_value="A funny gaming moment.")
    @patch.object(clipforge_app, "generate_shorts_metadata")
    def test_nvidia_workflow(self, metadata, transcribe, save):
        metadata.return_value = {
            "title": "Gaming Chaos in 30 Seconds",
            "description": "A quick funny gaming moment.",
            "hashtags": ["#shorts", "#gaming"],
            "hook": "Wait for the ending.",
            "pinned_comment": "Rate this moment.",
        }
        connect = self.client.post("/api/nvidia/connect", json={"api_key": "nvapi-long-test-key-value"})
        self.assertEqual(connect.status_code, 200)
        transcript = self.client.post("/api/nvidia/transcribe", json={"filename": "clip.mp4"})
        self.assertEqual(transcript.get_json()["transcript"], "A funny gaming moment.")
        generated = self.client.post(
            "/api/nvidia/generate-metadata",
            json={"transcript": "A funny gaming moment.", "language": "English", "tone": "Funny"},
        )
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.get_json()["metadata"]["title"], "Gaming Chaos in 30 Seconds")
        save.assert_called_once()
        transcribe.assert_called_once()

    def test_clear_library(self):
        with open(os.path.join(self.outputs, "delete-me.mp4"), "wb") as handle:
            handle.write(b"video")
        response = self.client.post("/api/clear-library")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["deleted"], 1)


if __name__ == "__main__":
    unittest.main()
