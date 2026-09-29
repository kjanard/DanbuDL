import unittest
from core.api import DanbooruAPI


class TestDanbooruLiveIntegration(unittest.TestCase):
    """Live online integration tests against Danbooru API."""
    def setUp(self):
        self.api = DanbooruAPI(delay=1.0)

    def test_live_autocomplete(self):
        """Verify live autocomplete returns valid suggestions from Danbooru."""
        suggestions = self.api.get_autocomplete("miku", limit=3)
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any("miku" in s["value"] for s in suggestions))

    def test_live_search_single_post(self):
        """Verify live search returns a valid post with metadata from Danbooru."""
        posts = self.api.search_posts(tags="hatsune_miku solo", ratings=["g"], limit=1)
        self.assertIsInstance(posts, list)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertIn("id", post)
        self.assertEqual(post.get("rating"), "g")
        self.assertTrue(bool(post.get("file_url") or post.get("large_file_url") or post.get("preview_file_url")))


if __name__ == "__main__":
    unittest.main()
