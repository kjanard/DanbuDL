import time
import json
import threading
import logging
import requests
from typing import List, Dict, Any, Optional
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("DanbuDL.API")


class DanbooruAPI:
    """
    Danbooru REST API Client adhering to official guidelines:
    - User-Agent identification standard
    - HTTP Basic Authentication (RFC 7617)
    - Thread-safe rate limiting (recommended ~1 request per second)
    - Query caching for Autocomplete and repeated queries
    - Cursor-based deep pagination (b<id>) to avoid 410 Gone
    - Exponential backoff on HTTP 429 (User Throttled) / 5xx
    """
    BASE_URL = "https://danbooru.donmai.us"
    APP_VERSION = "1.2"

    def __init__(self, username: str = "", api_key: str = "", delay: float = 1.0):
        self.username = username.strip()
        self.api_key = api_key.strip()
        self.delay = max(0.5, delay)
        self.last_request_time = 0.0
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {}

        self.session = requests.Session()
        self._update_session_auth_and_headers()

    def _update_session_auth_and_headers(self):
        """Configure User-Agent and Basic Auth according to Danbooru specifications."""
        if self.username:
            user_agent = f"DanbuDownloader/{self.APP_VERSION} (user: {self.username}; +https://danbooru.donmai.us/)"
        else:
            user_agent = f"DanbuDownloader/{self.APP_VERSION} (anonymous; +https://danbooru.donmai.us/)"

        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
        })

        if self.username and self.api_key:
            self.session.auth = HTTPBasicAuth(self.username, self.api_key)
        else:
            self.session.auth = None

    def update_credentials(self, username: str, api_key: str):
        self.username = username.strip()
        self.api_key = api_key.strip()
        self._update_session_auth_and_headers()

    def set_delay(self, delay: float):
        self.delay = max(0.5, delay)

    def _wait_rate_limit(self):
        """Enforce polite rate limiting between requests (thread-safe, recommended ~1 request per second)."""
        with self._lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def _request_with_retry(self, method: str, url: str, params: Optional[Dict] = None, max_retries: int = 4, **kwargs) -> requests.Response:
        """Execute HTTP request with exponential backoff on 429, 410, or transient server errors."""
        params = params or {}
        backoff = 2.0

        for attempt in range(max_retries):
            self._wait_rate_limit()
            try:
                response = self.session.request(method, url, params=params, timeout=20, **kwargs)

                # Inspect x-rate-limit if provided
                if "x-rate-limit" in response.headers:
                    try:
                        rate_info = json.loads(response.headers["x-rate-limit"])
                        # Optional: can log or adapt delay if pool is low
                    except Exception:
                        pass

                if response.status_code == 429:
                    # 429 User Throttled
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after else backoff
                    logger.warning(f"429 User Throttled. Backing off for {wait_time:.1f}s (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    backoff *= 2
                    continue

                if response.status_code in (500, 502, 503, 504):
                    # Server errors or Downbooru
                    logger.warning(f"Server status {response.status_code}. Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= 1.5
                    continue

                return response

            except (requests.ConnectionError, requests.Timeout) as e:
                logger.warning(f"Network connection issue: {e}. Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 1.5

        # Last attempt
        self._wait_rate_limit()
        return self.session.request(method, url, params=params, timeout=25, **kwargs)

    def search_posts(
        self,
        tags: str = "",
        ratings: Optional[List[str]] = None,
        limit: int = 50,
        page: Any = 1,
        order: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts matching tags and optional ratings.
        page can be numeric (e.g. 1) or cursor string (e.g. 'b12345' for posts before ID #12345).
        """
        tag_list = [t.strip() for t in tags.split() if t.strip()]

        # Handle ratings if specified
        if ratings and len(ratings) > 0 and len(ratings) < 4:
            has_rating = any(t.startswith("rating:") for t in tag_list)
            if not has_rating:
                tag_list.append(f"rating:{','.join(ratings)}")

        # Handle ordering
        if order and not any(t.startswith("order:") for t in tag_list):
            tag_list.append(f"order:{order}")

        query_tags = " ".join(tag_list)
        params = {
            "limit": min(limit, 200),
            "page": page
        }
        if query_tags:
            params["tags"] = query_tags

        url = f"{self.BASE_URL}/posts.json"
        response = self._request_with_retry("GET", url, params=params)

        if response.status_code == 200:
            posts = response.json()
            if isinstance(posts, list):
                # Extra client-side rating filter to guarantee exact match
                if ratings and len(ratings) > 0 and len(ratings) < 4:
                    posts = [p for p in posts if p.get("rating") in ratings]
                return posts
            return []
        elif response.status_code == 410:
            # 410 Gone: Pagination limit reached
            raise ValueError("Danbooru Pagination Limit (410 Gone). Use cursor pagination (b<id>) to search deeper.")
        elif response.status_code == 422:
            # 422 Unprocessable / Tag limit
            err_msg = response.text
            try:
                err_json = response.json()
                err_msg = err_json.get("message", response.text)
            except Exception:
                pass
            raise ValueError(f"Danbooru API Error (422): {err_msg}")
        elif response.status_code == 401:
            raise PermissionError("Danbooru Unauthorized (401). Invalid username or API key.")
        elif response.status_code == 403:
            raise PermissionError("Danbooru Access Forbidden (403). Safe mode or permission restriction.")
        else:
            response.raise_for_status()
            return []

    def get_post_by_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single post by ID: GET /posts/:id.json"""
        url = f"{self.BASE_URL}/posts/{post_id}.json"
        response = self._request_with_retry("GET", url)
        if response.status_code == 200:
            return response.json()
        return None

    def get_pool(self, pool_id: int) -> Optional[Dict[str, Any]]:
        """Fetch pool details: GET /pools/:id.json"""
        url = f"{self.BASE_URL}/pools/{pool_id}.json"
        response = self._request_with_retry("GET", url)
        if response.status_code == 200:
            return response.json()
        return None

    def get_related_tags(self, query: str) -> List[Dict[str, Any]]:
        """Fetch related tags: GET /related_tag.json?query=..."""
        url = f"{self.BASE_URL}/related_tag.json"
        params = {"query": query}
        try:
            res = self._request_with_retry("GET", url, params=params)
            if res.status_code == 200:
                data = res.json()
                return data.get("related_tags", [])
        except Exception as e:
            logger.debug(f"[RelatedTags] Error: {e}")
        return []

    def get_autocomplete(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Query tag autocomplete suggestions: GET /autocomplete.json"""
        clean_query = query.strip().lower()
        if not clean_query or len(clean_query) < 1:
            return []

        cache_key = f"{clean_query}_{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = f"{self.BASE_URL}/autocomplete.json"
        params = {
            "search[query]": clean_query,
            "search[type]": "tag_query",
            "version": "1",
            "limit": limit
        }

        try:
            self._wait_rate_limit()
            res = self.session.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                results = []
                for item in data:
                    results.append({
                        "label": item.get("label") or item.get("value"),
                        "value": item.get("value"),
                        "post_count": item.get("post_count", 0),
                        "category": item.get("category", 0)
                    })
                self._cache[cache_key] = results
                return results
        except Exception as e:
            logger.debug(f"Autocomplete Error: {e}")
        return []

    def get_preview_image(self, url: str) -> Optional[bytes]:
        """Fetch thumbnail or preview image bytes."""
        if not url:
            return None
        try:
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                return res.content
        except Exception as e:
            logger.debug(f"[Preview] Error fetching {url}: {e}")
        return None
