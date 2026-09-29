import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from core.api import DanbooruAPI


def sanitize_filename(name: str) -> str:
    """Sanitize string for Windows filesystem."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name)
    sanitized = sanitized.strip(" ._")
    return sanitized if sanitized else "unnamed"


class FetchWorker(QObject):
    """
    Worker to fetch post metadata in background adhering to Danbooru API guidelines:
    - Automatically handles single post URLs (e.g. https://danbooru.donmai.us/posts/123)
    - Automatically handles pool URLs or tags (e.g. pool:31957)
    - Uses cursor pagination (b<id>) to safely fetch large quantities without hitting 410 Gone
    """
    started = pyqtSignal()
    progress = pyqtSignal(int, int)  # fetched_count, target_count
    finished = pyqtSignal(list)       # list of post dicts
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)        # level, message

    def __init__(self, api: DanbooruAPI, tags: str, ratings: List[str], target_limit: int, order: str = "id_desc"):
        super().__init__()
        self.api = api
        self.tags = tags.strip()
        self.ratings = ratings
        self.target_limit = target_limit
        self.order = order
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        self.started.emit()
        all_posts = []

        try:
            # Check if input is a direct post URL: https://danbooru.donmai.us/posts/12345
            post_url_match = re.search(r'danbooru\.donmai\.us/posts/(\d+)', self.tags)
            if post_url_match:
                post_id = int(post_url_match.group(1))
                self.log.emit("INFO", f"Detected Danbooru Post URL for Post #{post_id}...")
                post = self.api.get_post_by_id(post_id)
                if post:
                    all_posts.append(post)
                    self.log.emit("SUCCESS", f"Found post #{post_id}.")
                else:
                    self.log.emit("WARNING", f"Post #{post_id} not found or restricted.")
                self.finished.emit(all_posts)
                return

            # Check if input is a direct pool URL: https://danbooru.donmai.us/pools/12345
            pool_url_match = re.search(r'danbooru\.donmai\.us/pools/(\d+)', self.tags)
            if pool_url_match:
                pool_id = pool_url_match.group(1)
                self.tags = f"pool:{pool_id}"
                self.log.emit("INFO", f"Converted Danbooru Pool URL to search tag 'pool:{pool_id}'...")

            self.log.emit("INFO", f"Searching Danbooru for: '{self.tags}' (Ratings: {', '.join(self.ratings) if self.ratings else 'All'})")

            cursor_page: Any = 1
            batch_size = min(200, self.target_limit)

            while len(all_posts) < self.target_limit and not self.is_cancelled:
                needed = self.target_limit - len(all_posts)
                current_batch = min(200, needed)

                posts = self.api.search_posts(
                    tags=self.tags,
                    ratings=self.ratings,
                    limit=current_batch,
                    page=cursor_page,
                    order=self.order
                )

                if not posts:
                    self.log.emit("INFO", "No more matching posts found.")
                    break

                existing_ids = {p["id"] for p in all_posts}
                new_posts = [p for p in posts if p["id"] not in existing_ids]

                if not new_posts:
                    break

                all_posts.extend(new_posts)
                self.progress.emit(len(all_posts), self.target_limit)
                self.log.emit("DEBUG", f"Fetched {len(all_posts)} / {self.target_limit} posts...")

                if len(posts) < current_batch:
                    # Reached end of results
                    break

                # Official Danbooru pagination: use 'b<id>' to get posts before the last post ID
                # This prevents HTTP 410 Gone on deep searches!
                last_post_id = posts[-1].get("id")
                if last_post_id and (self.order == "id_desc" or "order:id_desc" in self.tags or not self.order):
                    cursor_page = f"b{last_post_id}"
                else:
                    # For score or non-id ordering, use numeric increment
                    if isinstance(cursor_page, int):
                        cursor_page += 1
                    else:
                        break

            if self.is_cancelled:
                self.log.emit("WARNING", "Fetch was cancelled by user.")
            else:
                self.log.emit("SUCCESS", f"Finished fetching {len(all_posts)} posts.")

            self.finished.emit(all_posts)

        except Exception as e:
            self.log.emit("ERROR", f"Fetch failed: {str(e)}")
            self.error.emit(str(e))


class DownloadWorker(QObject):
    """
    Worker to download files and metadata in background adhering to Danbooru guidelines:
    - Respects rate limiting delay (default 1.0s, CDN safe)
    - Saves metadata sidecar files (.txt format tailored for AI datasets or .json)
    - Safe resume & skip existing logic
    """
    started = pyqtSignal(int)                           # total items
    file_started = pyqtSignal(int, str, int, int)       # post_id, filename, current_idx, total
    file_progress = pyqtSignal(int, int, int, float)    # post_id, downloaded_bytes, total_bytes, speed_bps
    file_completed = pyqtSignal(int, str, str)          # post_id, filename, status ('downloaded', 'skipped', 'failed', 'restricted')
    all_completed = pyqtSignal(dict)                    # summary stats
    preview_loaded = pyqtSignal(int, bytes)             # post_id, image_bytes
    log = pyqtSignal(str, str)                          # level, message

    def __init__(
        self,
        api: DanbooruAPI,
        posts: List[Dict[str, Any]],
        download_dir: str,
        skip_existing: bool = True,
        save_metadata: bool = True,
        metadata_format: str = "txt",
        quality: str = "original",
        naming_format: str = "{id}_{md5}.{ext}",
        delay: float = 1.0
    ):
        super().__init__()
        self.api = api
        self.posts = posts
        self.download_dir = Path(download_dir)
        self.skip_existing = skip_existing
        self.save_metadata = save_metadata
        self.metadata_format = metadata_format
        self.quality = quality
        self.naming_format = naming_format
        self.delay = max(0.5, delay)

        self.is_cancelled = False
        self.is_paused = False

    def cancel(self):
        self.is_cancelled = True

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def run(self):
        total = len(self.posts)
        self.started.emit(total)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        skipped = 0
        failed = 0

        self.log.emit("INFO", f"Starting batch download for {total} files into '{self.download_dir}'...")

        for idx, post in enumerate(self.posts, start=1):
            if self.is_cancelled:
                self.log.emit("WARNING", "Download cancelled by user.")
                break

            while self.is_paused and not self.is_cancelled:
                time.sleep(0.3)

            post_id = post.get("id")

            # Determine image URL
            url = None
            if self.quality == "original" and post.get("file_url"):
                url = post["file_url"]
            elif post.get("large_file_url"):
                url = post["large_file_url"]
            elif post.get("file_url"):
                url = post["file_url"]
            elif post.get("preview_file_url"):
                url = post["preview_file_url"]

            if not url:
                self.log.emit("WARNING", f"Post #{post_id} has no accessible file URL (Banned or Account-restricted).")
                self.file_completed.emit(post_id, f"post_{post_id}", "restricted")
                failed += 1
                continue

            ext = post.get("file_ext") or url.split("?")[0].split(".")[-1] or "jpg"
            md5 = post.get("md5") or ""
            artist = sanitize_filename(post.get("tag_string_artist") or "unknown")
            if len(artist) > 50:
                artist = artist[:50]

            filename = self.naming_format.format(
                id=post_id,
                md5=md5,
                artist=artist,
                ext=ext
            )
            filename = sanitize_filename(filename)
            dest_path = self.download_dir / filename

            self.file_started.emit(post_id, filename, idx, total)

            # Skip existing files
            if self.skip_existing and dest_path.exists() and dest_path.stat().st_size > 0:
                self.log.emit("DEBUG", f"Post #{post_id} already exists ({filename}). Skipping.")
                self.file_completed.emit(post_id, filename, "skipped")
                skipped += 1
                if self.save_metadata:
                    self._save_metadata(post, dest_path)
                continue

            # Download file
            success = self._download_single_file(url, dest_path, post_id)

            if success:
                downloaded += 1
                if self.save_metadata:
                    self._save_metadata(post, dest_path)
                self.file_completed.emit(post_id, filename, "downloaded")
            else:
                failed += 1
                self.file_completed.emit(post_id, filename, "failed")

            # Polite delay between file requests (Danbooru best practice)
            time.sleep(self.delay)

        summary = {
            "total": total,
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "cancelled": self.is_cancelled
        }
        self.all_completed.emit(summary)
        self.log.emit("SUCCESS", f"Download finished. {downloaded} downloaded, {skipped} skipped, {failed} failed.")

    def _download_single_file(self, url: str, dest_path: Path, post_id: int) -> bool:
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
        try:
            with self.api.session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                try:
                    total_bytes = int(r.headers.get("Content-Length", 0))
                except (ValueError, TypeError):
                    total_bytes = 0

                downloaded_bytes = 0
                start_time = time.time()
                last_emit_time = start_time

                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if self.is_cancelled:
                            tmp_path.unlink(missing_ok=True)
                            return False

                        while self.is_paused and not self.is_cancelled:
                            time.sleep(0.3)

                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)

                            now = time.time()
                            if now - last_emit_time > 0.15:
                                elapsed = max(0.001, now - start_time)
                                speed = downloaded_bytes / elapsed
                                self.file_progress.emit(post_id, downloaded_bytes, total_bytes, speed)
                                last_emit_time = now

            if tmp_path.exists():
                tmp_path.replace(dest_path)
                return True

        except Exception as e:
            self.log.emit("ERROR", f"Error downloading #{post_id}: {str(e)}")
            tmp_path.unlink(missing_ok=True)
            return False

        return False

    def _save_metadata(self, post: Dict[str, Any], image_path: Path):
        """Save metadata sidecar file (.txt or .json)."""
        try:
            if self.metadata_format == "json":
                meta_file = image_path.with_suffix(".json")
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(post, f, indent=2, ensure_ascii=False)
            else:
                # Text format: space separated tags for AI dataset / SD LoRA training
                meta_file = image_path.with_suffix(".txt")
                tag_string = post.get("tag_string", "")
                with open(meta_file, "w", encoding="utf-8") as f:
                    f.write(tag_string)
        except Exception as e:
            self.log.emit("WARNING", f"Failed to save metadata for #{post.get('id')}: {e}")
