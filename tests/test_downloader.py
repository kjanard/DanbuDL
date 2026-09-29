import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.api import DanbooruAPI
from core.downloader import sanitize_filename, FetchWorker, DownloadWorker


class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.download_dir = Path(self.temp_dir.name)
        self.api = DanbooruAPI(delay=0.05)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_filename(self):
        """Test Windows illegal characters and edge cases."""
        self.assertEqual(sanitize_filename('artist/name:foo*bar?test"ok<1>2|3'), "artist_name_foo_bar_test_ok_1_2_3")
        self.assertEqual(sanitize_filename("... leading and trailing dots ..."), "leading and trailing dots")
        self.assertEqual(sanitize_filename(""), "unnamed")
        self.assertEqual(sanitize_filename(":::"), "unnamed")

    def test_fetch_worker_single_post_url(self):
        """Test FetchWorker extracting post ID from Danbooru URL."""
        mock_api = MagicMock()
        mock_api.get_post_by_id.return_value = {"id": 12345, "rating": "g", "tag_string": "test"}

        worker = FetchWorker(
            api=mock_api,
            tags="https://danbooru.donmai.us/posts/12345",
            ratings=[],
            target_limit=1
        )

        results = []
        worker.finished.connect(lambda posts: results.extend(posts))
        worker.run()

        mock_api.get_post_by_id.assert_called_once_with(12345)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 12345)

    def test_fetch_worker_pool_url(self):
        """Test FetchWorker converting pool URL to pool tag."""
        mock_api = MagicMock()
        mock_api.search_posts.return_value = [
            {"id": 101, "rating": "g"},
            {"id": 102, "rating": "g"}
        ]

        worker = FetchWorker(
            api=mock_api,
            tags="https://danbooru.donmai.us/pools/999",
            ratings=[],
            target_limit=2
        )

        results = []
        worker.finished.connect(lambda posts: results.extend(posts))
        worker.run()

        mock_api.search_posts.assert_called_once()
        self.assertEqual(mock_api.search_posts.call_args[1]["tags"], "pool:999")
        self.assertEqual(len(results), 2)

    def test_download_worker_save_file_and_txt_metadata(self):
        """Test downloading mock file and creating .txt sidecar."""
        sample_post = {
            "id": 9999,
            "md5": "abc123md5",
            "file_ext": "jpg",
            "tag_string_artist": "super_artist",
            "file_url": "https://cdn.donmai.us/dummy/image.jpg",
            "tag_string": "tag1 tag2 tag3"
        }

        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "12"}
        mock_response.iter_content.return_value = [b"mock_image_data"]

        with patch("time.sleep"), patch.object(self.api.session, "get", return_value=mock_response):
            worker = DownloadWorker(
                api=self.api,
                posts=[sample_post],
                download_dir=str(self.download_dir),
                skip_existing=False,
                save_metadata=True,
                metadata_format="txt",
                delay=0.01
            )
            completed_events = []
            worker.file_completed.connect(lambda pid, fn, status: completed_events.append((pid, status)))
            worker.run()

        self.assertEqual(len(completed_events), 1)
        self.assertEqual(completed_events[0][1], "downloaded")

        # Verify files on disk
        img_file = self.download_dir / "9999_abc123md5.jpg"
        txt_file = self.download_dir / "9999_abc123md5.txt"

        self.assertTrue(img_file.exists())
        self.assertEqual(img_file.read_bytes(), b"mock_image_data")

        self.assertTrue(txt_file.exists())
        self.assertEqual(txt_file.read_text(encoding="utf-8"), "tag1 tag2 tag3")

    def test_download_worker_save_json_metadata(self):
        """Test downloading and saving .json sidecar metadata."""
        sample_post = {
            "id": 8888,
            "md5": "jsonmd5",
            "file_ext": "png",
            "file_url": "https://cdn.donmai.us/dummy/image.png",
            "tag_string": "cool_tag",
            "score": 42
        }

        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "8"}
        mock_response.iter_content.return_value = [b"pngbytes"]

        with patch("time.sleep"), patch.object(self.api.session, "get", return_value=mock_response):
            worker = DownloadWorker(
                api=self.api,
                posts=[sample_post],
                download_dir=str(self.download_dir),
                save_metadata=True,
                metadata_format="json",
                delay=0.01
            )
            worker.run()

        json_file = self.download_dir / "8888_jsonmd5.json"
        self.assertTrue(json_file.exists())
        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], 8888)
        self.assertEqual(data["score"], 42)

    @patch("time.sleep")
    def test_download_worker_skip_existing(self, mock_sleep):
        """Test skipping files that already exist."""
        existing_file = self.download_dir / "7777_existmd5.jpg"
        existing_file.write_bytes(b"existing_file_content")

        sample_post = {
            "id": 7777,
            "md5": "existmd5",
            "file_ext": "jpg",
            "file_url": "https://cdn.donmai.us/dummy/image.jpg",
            "tag_string": "tag"
        }

        worker = DownloadWorker(
            api=self.api,
            posts=[sample_post],
            download_dir=str(self.download_dir),
            skip_existing=True,
            delay=0.01
        )
        completed_status = []
        worker.file_completed.connect(lambda pid, fn, st: completed_status.append(st))
        worker.run()

        self.assertEqual(completed_status, ["skipped"])
        # Original content unchanged
        self.assertEqual(existing_file.read_bytes(), b"existing_file_content")

    @patch("time.sleep")
    def test_download_worker_restricted_url(self, mock_sleep):
        """Test handling posts with no accessible image URL (banned / locked)."""
        banned_post = {
            "id": 6666,
            "is_banned": True
            # No file_url, large_file_url, or preview_file_url
        }

        worker = DownloadWorker(
            api=self.api,
            posts=[banned_post],
            download_dir=str(self.download_dir),
            delay=0.01
        )
        completed_status = []
        worker.file_completed.connect(lambda pid, fn, st: completed_status.append(st))
        worker.run()

        self.assertEqual(completed_status, ["restricted"])


if __name__ == "__main__":
    unittest.main()
