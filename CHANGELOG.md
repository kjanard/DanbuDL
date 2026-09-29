# Changelog

All notable changes to the **DanbuDL: Danbooru Downloader** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-09-29

### Added
- **Rating "All" Toggle**: Added a master checkbox for Rating filters that toggles all rating categories (`General`, `Sensitive`, `Questionable`, `Explicit`) simultaneously with bidirectional state synchronization.
- **Danbooru Pool & Post URL Support**:
  - Automatically recognizes and downloads entire Danbooru Pools by pasting a pool URL (e.g., `https://danbooru.donmai.us/pools/31957`) or tag `pool:31957`.
  - Automatically parses single Post URLs (e.g., `https://danbooru.donmai.us/posts/12345`).
- **Cursor-based Deep Pagination (`b<id>`)**: Implemented Danbooru's official pagination standard using `page=b{last_post_id}` to prevent `HTTP 410 Gone` errors on searches with large result sets.
- **Vector Assets (`assets/check.svg`)**: Added SVG checkmark asset for crisp rendering across all Windows High-DPI scaling levels.
- **Official Branding Artwork (`icon/`)**: Added official application icon and high-resolution logo artwork (`logo.jpg`, `logo2.jpg`).
- **Custom Non-Commercial & Share-Alike License (NC-SA 1.0)**: Added explicit open-source license protecting personal and educational usage while prohibiting commercial exploitation.
- **GitHub-Ready Repository Setup**: Configured comprehensive `.gitignore`, provided `config.example.json` template, and wrote detailed installation & usage documentation.
- **Automated Unit & Integration Test Suite**: Created complete test coverage with 27 unit and integration tests under `tests/` testing ConfigManager, DanbooruAPI, FetchWorker, DownloadWorker, live endpoints, and PyQt6 UI components.
- **Strict Thread-Safe Rate Limiter & Concurrency Protection**: Added `threading.Lock()` to `_wait_rate_limit()`, clamped minimum request delay to 0.5s to prevent accidental spamming, and added duplicate fetch request guards.
- **Smart Autocomplete Query Caching & Debounce**: Increased debounce delay to 450ms and introduced dual-layer in-memory caching to eliminate redundant Danbooru API requests while typing.

### Fixed
- **Clean Test Execution & Log Silencing**: Silenced mock test 429 warnings by routing logs through `logging.getLogger` and `assertLogs`, eliminating false-alarm throttling messages in the terminal during unit tests.
- **QFSFileEngine Warning**: Eliminated the recurring `QFSFileEngine::open: No file name specified` terminal warning caused by an empty `url("")` declaration in the checkbox stylesheet indicator.
- **Thread Lifecycle Cleanup (`QThread Destroyed`)**: Resolved `QThread: Destroyed while thread '' is still running` crash on window close by adding graceful cleanup hooks for `AutocompleteWorker` and `PreviewLoader` background threads.
- **Config Isolation**: Used `copy.deepcopy` to prevent shared nested configuration dictionary mutation.
- **Filename Sanitization Fallback**: Handled edge cases where illegal characters or dots stripped down to empty names with a safe fallback.

### Changed
- **Rebranded Application**: Renamed application to **DanbuDL: Danbooru Downloader** across all UI titles, headers, and docs.
- **Official API User-Agent**: Updated User-Agent header to comply strictly with Danbooru's bot guidelines (`DanbuDownloader/1.1 (user: <username>)`).
- **HTTP Basic Authentication**: Migrated API credentials to RFC 7617 HTTP Basic Authentication instead of passing sensitive keys via URL query parameters.
- **API Compliance Documentation**: Added dedicated section and notice in README.md detailing compliance with Danbooru's official developer guidelines (Help:API and Help:User Scripts).

---

## [1.1.0] - 2026-09-29

### Added
- **API Guidelines Compliance**: Researched and integrated recommendations from Danbooru's official `help:api` and `help:user_scripts` documentation.
- **Enhanced Rate Limiting**: Added exponential backoff and retry handling for `429 User Throttled` and server downtime (`500/502/503`).
- **Validation**: Added validation warning when fetching without any selected rating category.

---

## [1.0.0] - 2026-09-29

### Added
- **Initial Release of Danbooru Downloader Desktop GUI**:
  - Built with Python 3.12 and PyQt6 with an eye-catching modern Dark Mode interface.
  - Tag Search with smart real-time autocomplete querying `/autocomplete.json` with category color coding (Artist, Character, Copyright, General).
  - Rating filters (General, Sensitive, Questionable, Explicit).
  - Configurable Request Delay slider (0.2s - 3.0s, default 1.0s) to politely avoid IP bans.
  - Multithreaded background fetch and download workers (`QThread`) with Start, Pause, Resume, and Cancel capabilities.
  - Sidecar metadata export (`.txt` for AI dataset / SD LoRA training, `.json` for full metadata).
  - Skip existing downloaded files (Resume support).
  - Live Preview Panel with thumbnail decoding, detailed metadata, tag list, and quick buttons to open in browser or local folder.
  - Persistent settings management via `config.json`.
