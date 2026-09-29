import unittest
from unittest.mock import MagicMock, patch
import requests
from core.api import DanbooruAPI


class TestDanbooruAPI(unittest.TestCase):
    def setUp(self):
        self.api = DanbooruAPI(username="", api_key="", delay=0.1)

    def test_anonymous_user_agent(self):
        """Test anonymous User-Agent conforms to Danbooru specifications."""
        ua = self.api.session.headers.get("User-Agent", "")
        self.assertIn("DanbuDownloader", ua)
        self.assertIn("anonymous", ua)
        self.assertIsNone(self.api.session.auth)

    def test_authenticated_user_agent_and_basic_auth(self):
        """Test authenticated user agent and HTTP Basic Auth setup."""
        api = DanbooruAPI(username="artist123", api_key="secretkey", delay=0.1)
        ua = api.session.headers.get("User-Agent", "")
        self.assertIn("user: artist123", ua)
        self.assertIsNotNone(api.session.auth)
        self.assertEqual(api.session.auth.username, "artist123")
        self.assertEqual(api.session.auth.password, "secretkey")

    def test_delay_limits(self):
        """Test delay cannot be set to negative or dangerously small values."""
        self.api.set_delay(0.01)
        self.assertGreaterEqual(self.api.delay, 0.5)

    @patch("requests.Session.request")
    def test_search_posts_params_and_cursor(self, mock_request):
        """Test query construction with rating and cursor pagination."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 100, "rating": "g", "tag_string": "test_tag"}
        ]
        mock_request.return_value = mock_response

        posts = self.api.search_posts(
            tags="miku solo",
            ratings=["g", "s"],
            limit=50,
            page="b123456",
            order="id_desc"
        )

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        params = call_kwargs["params"]

        self.assertEqual(params["limit"], 50)
        self.assertEqual(params["page"], "b123456")
        self.assertIn("miku", params["tags"])
        self.assertIn("solo", params["tags"])
        self.assertIn("rating:g,s", params["tags"])
        self.assertIn("order:id_desc", params["tags"])
        self.assertEqual(len(posts), 1)

    @patch("time.sleep")
    @patch("requests.Session.request")
    def test_retry_on_429_throttled(self, mock_request, mock_sleep):
        """Test exponential backoff retry when receiving 429 User Throttled."""
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "0.1"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = [{"id": 1, "rating": "g"}]

        # First returns 429, second returns 200
        mock_request.side_effect = [resp_429, resp_200]

        with self.assertLogs("DanbuDL.API", level="WARNING") as cm:
            posts = self.api.search_posts(tags="test", limit=1)

        self.assertEqual(len(posts), 1)
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_any_call(0.1)
        self.assertTrue(any("429 User Throttled" in log for log in cm.output))

    @patch("requests.Session.request")
    def test_pagination_limit_410_gone(self, mock_request):
        """Test 410 Gone error handling."""
        resp_410 = MagicMock()
        resp_410.status_code = 410
        mock_request.return_value = resp_410

        with self.assertRaises(ValueError) as ctx:
            self.api.search_posts(tags="test", page=1000)
        self.assertIn("410 Gone", str(ctx.exception))

    @patch("requests.Session.request")
    def test_permission_error_401(self, mock_request):
        """Test 401 Unauthorized error handling."""
        resp_401 = MagicMock()
        resp_401.status_code = 401
        mock_request.return_value = resp_401

        with self.assertRaises(PermissionError):
            self.api.search_posts(tags="test")

    @patch("requests.Session.get")
    def test_autocomplete_formatting(self, mock_get):
        """Test parsing of autocomplete suggestions."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"label": "hatsune_miku", "value": "hatsune_miku", "post_count": 140000, "category": 4}
        ]
        mock_get.return_value = mock_resp

        results = self.api.get_autocomplete("miku", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["value"], "hatsune_miku")
        self.assertEqual(results[0]["category"], 4)
        self.assertEqual(results[0]["post_count"], 140000)


if __name__ == "__main__":
    unittest.main()
