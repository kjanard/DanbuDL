import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QSlider, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QMessageBox, QMenu, QTabWidget, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QAction, QIcon

from core.api import DanbooruAPI
from core.config import ConfigManager
from core.downloader import FetchWorker, DownloadWorker, sanitize_filename
from ui.styles import DARK_THEME_QSS
from ui.widgets import TagAutoCompleteLineEdit, RatingBadge, RATING_COLORS
from ui.preview_panel import PreviewPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DanbuDL: Danbooru Downloader")
        self.resize(1280, 840)
        self.setMinimumSize(960, 640)

        self.config_manager = ConfigManager()
        self.api = DanbooruAPI(
            username=self.config_manager.get("api_username", ""),
            api_key=self.config_manager.get("api_key", ""),
            delay=self.config_manager.get("request_delay", 1.0)
        )

        self.fetched_posts: List[Dict[str, Any]] = []
        self.post_row_map: Dict[int, int] = {}  # post_id -> table row
        self.downloaded_paths: Dict[int, str] = {}  # post_id -> local filepath

        # Workers & Threads
        self.fetch_thread: Optional[QThread] = None
        self.fetch_worker: Optional[FetchWorker] = None
        self.download_thread: Optional[QThread] = None
        self.download_worker: Optional[DownloadWorker] = None

        self._init_ui()
        self._load_settings()

        # Apply dark theme
        self.setStyleSheet(DARK_THEME_QSS)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # 1. Header Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel("DanbuDL: Danbooru Downloader")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;")
        sub_lbl = QLabel("Polite, high-speed anime art downloader with rate limiting & metadata export")
        sub_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)
        header.addStretch()

        self.status_pill = QLabel("Ready")
        self.status_pill.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 4px 14px;
            font-weight: 600;
        """)
        header.addWidget(self.status_pill)
        main_layout.addLayout(header)

        # 2. Search & Filter Card
        search_card = QGroupBox("Search & Tag Filters")
        search_layout = QVBoxLayout(search_card)
        search_layout.setSpacing(10)

        # First row: Tag input with autocomplete + Fetch Button
        tag_row = QHBoxLayout()
        tag_row.setSpacing(8)

        lbl_tags = QLabel("Tags:")
        lbl_tags.setStyleSheet("font-weight: 600; min-width: 45px;")
        tag_row.addWidget(lbl_tags)

        self.tag_input = TagAutoCompleteLineEdit(self.api)
        self.tag_input.setPlaceholderText("Enter tags, Post URL, or Pool URL/tag (e.g. 'hatsune_miku solo', 'pool:31957', or post URL)")
        self.tag_input.returnPressed.connect(self._start_fetch)
        tag_row.addWidget(self.tag_input, 1)

        self.btn_fetch = QPushButton("🔍 Search Posts")
        self.btn_fetch.setObjectName("primaryBtn")
        self.btn_fetch.setMinimumWidth(130)
        self.btn_fetch.clicked.connect(self._start_fetch)
        tag_row.addWidget(self.btn_fetch)

        search_layout.addLayout(tag_row)

        # Second row: Rating checkboxes + Limit + Order
        filter_row = QHBoxLayout()
        filter_row.setSpacing(16)

        lbl_rating = QLabel("Rating:")
        lbl_rating.setStyleSheet("font-weight: 600;")
        filter_row.addWidget(lbl_rating)

        self.chk_all = QCheckBox("All")
        self.chk_all.setStyleSheet("font-weight: 700; color: #38bdf8;")
        self.chk_all.toggled.connect(self._on_all_ratings_toggled)

        self.chk_g = QCheckBox("General (g)")
        self.chk_s = QCheckBox("Sensitive (s)")
        self.chk_q = QCheckBox("Questionable (q)")
        self.chk_e = QCheckBox("Explicit (e)")

        for chk in (self.chk_g, self.chk_s, self.chk_q, self.chk_e):
            chk.toggled.connect(self._on_individual_rating_toggled)

        filter_row.addWidget(self.chk_all)
        filter_row.addWidget(self.chk_g)
        filter_row.addWidget(self.chk_s)
        filter_row.addWidget(self.chk_q)
        filter_row.addWidget(self.chk_e)

        filter_row.addSpacing(15)

        lbl_limit = QLabel("Limit:")
        lbl_limit.setStyleSheet("font-weight: 600;")
        filter_row.addWidget(lbl_limit)

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 1000)
        self.spin_limit.setValue(50)
        self.spin_limit.setFixedWidth(80)
        filter_row.addWidget(self.spin_limit)

        lbl_order = QLabel("Order:")
        lbl_order.setStyleSheet("font-weight: 600;")
        filter_row.addWidget(lbl_order)

        self.cmb_order = QComboBox()
        self.cmb_order.addItems(["id_desc (Newest)", "score (Top Rated)", "favcount (Most Favorited)", "id_asc (Oldest)"])
        filter_row.addWidget(self.cmb_order)

        filter_row.addStretch()
        search_layout.addLayout(filter_row)
        main_layout.addWidget(search_card)

        # 3. Settings Card (Collapsible / Compact)
        settings_card = QGroupBox("Download Settings & Rate Limiting")
        set_layout = QVBoxLayout(settings_card)
        set_layout.setSpacing(8)

        # Row 1: Folder selection
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        lbl_dir = QLabel("Save Folder:")
        lbl_dir.setStyleSheet("font-weight: 600; min-width: 80px;")
        dir_row.addWidget(lbl_dir)

        self.txt_dir = QLineEdit()
        self.txt_dir.setReadOnly(True)
        dir_row.addWidget(self.txt_dir, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.btn_browse)

        self.btn_open_dir = QPushButton("Open Folder")
        self.btn_open_dir.clicked.connect(self._open_dir)
        dir_row.addWidget(self.btn_open_dir)
        set_layout.addLayout(dir_row)

        # Row 2: Rate limit delay, Quality, Metadata, Skip existing
        options_row = QHBoxLayout()
        options_row.setSpacing(14)

        lbl_delay = QLabel("Rate Limit Delay:")
        lbl_delay.setStyleSheet("font-weight: 600;")
        options_row.addWidget(lbl_delay)

        self.slider_delay = QSlider(Qt.Orientation.Horizontal)
        self.slider_delay.setRange(5, 30)  # 0.5s to 3.0s (Polite Danbooru guideline)
        self.slider_delay.setValue(10)     # 1.0s
        self.slider_delay.setFixedWidth(130)
        self.slider_delay.valueChanged.connect(self._on_delay_changed)
        options_row.addWidget(self.slider_delay)

        self.lbl_delay_val = QLabel("1.0 s")
        self.lbl_delay_val.setStyleSheet("color: #38bdf8; font-weight: bold; min-width: 45px;")
        options_row.addWidget(self.lbl_delay_val)

        options_row.addSpacing(10)

        lbl_qual = QLabel("Quality:")
        lbl_qual.setStyleSheet("font-weight: 600;")
        options_row.addWidget(lbl_qual)

        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems(["Original File", "Sample (Large 850px)"])
        options_row.addWidget(self.cmb_quality)

        self.chk_skip = QCheckBox("Skip Existing")
        self.chk_skip.setChecked(True)
        options_row.addWidget(self.chk_skip)

        self.chk_meta = QCheckBox("Save Tags (.txt)")
        self.chk_meta.setChecked(True)
        self.chk_meta.setToolTip("Saves .txt sidecar file with tags for AI LoRA training / Stable Diffusion")
        options_row.addWidget(self.chk_meta)

        self.cmb_meta_fmt = QComboBox()
        self.cmb_meta_fmt.addItems([".txt format", ".json format"])
        options_row.addWidget(self.cmb_meta_fmt)

        options_row.addStretch()
        set_layout.addLayout(options_row)

        # Row 3: Danbooru API Auth (Optional)
        auth_row = QHBoxLayout()
        auth_row.setSpacing(10)
        self.chk_auth = QCheckBox("Use Danbooru Account (Optional - for higher tag limit)")
        self.chk_auth.toggled.connect(self._toggle_auth)
        auth_row.addWidget(self.chk_auth)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Danbooru Username")
        self.txt_username.setFixedWidth(160)
        self.txt_username.setEnabled(False)
        auth_row.addWidget(self.txt_username)

        self.txt_api_key = QLineEdit()
        self.txt_api_key.setPlaceholderText("API Key")
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setFixedWidth(200)
        self.txt_api_key.setEnabled(False)
        auth_row.addWidget(self.txt_api_key)

        self.btn_save_auth = QPushButton("Save Auth")
        self.btn_save_auth.setEnabled(False)
        self.btn_save_auth.clicked.connect(self._save_auth)
        auth_row.addWidget(self.btn_save_auth)

        auth_row.addStretch()
        set_layout.addLayout(auth_row)

        main_layout.addWidget(settings_card)

        # 4. Central Splitter (Table & Preview & Logs)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Tabs for Posts Table and Activity Log
        left_tabs = QTabWidget()

        # Tab 1: Posts Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["#", "ID", "Rating", "Artist", "Format", "Resolution", "Size", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        left_tabs.addTab(self.table, "📋 Posts Queue (0)")

        # Tab 2: Activity Logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        left_tabs.addTab(self.log_text, "📜 Activity Log")

        splitter.addWidget(left_tabs)

        # Right: Preview Panel
        self.preview_panel = PreviewPanel(self.api)
        self.preview_panel.setMinimumWidth(320)
        self.preview_panel.setMaximumWidth(460)
        splitter.addWidget(self.preview_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 1)

        # 5. Bottom Controls & Progress
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(8)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        self.btn_download = QPushButton("⬇️ Start Download")
        self.btn_download.setObjectName("successBtn")
        self.btn_download.setMinimumHeight(38)
        self.btn_download.setMinimumWidth(150)
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._start_download)
        ctrl_row.addWidget(self.btn_download)

        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setMinimumHeight(38)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        ctrl_row.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("⏹️ Cancel")
        self.btn_cancel.setObjectName("dangerBtn")
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_download)
        ctrl_row.addWidget(self.btn_cancel)

        ctrl_row.addSpacing(15)

        self.lbl_speed = QLabel("Speed: -")
        self.lbl_speed.setStyleSheet("color: #94a3b8; font-weight: 500;")
        ctrl_row.addWidget(self.lbl_speed)

        self.lbl_stats = QLabel("Downloaded: 0 / 0")
        self.lbl_stats.setStyleSheet("color: #38bdf8; font-weight: 600;")
        ctrl_row.addWidget(self.lbl_stats)

        ctrl_row.addStretch()
        bottom_box.addLayout(ctrl_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        bottom_box.addWidget(self.progress_bar)

        main_layout.addLayout(bottom_box)

    def _load_settings(self):
        download_dir = self.config_manager.get("download_dir", str(Path.cwd() / "downloads"))
        self.txt_dir.setText(download_dir)

        delay = float(self.config_manager.get("request_delay", 1.0))
        self.slider_delay.setValue(int(delay * 10))
        self.lbl_delay_val.setText(f"{delay:.1f} s")

        self.chk_skip.setChecked(self.config_manager.get("skip_existing", True))
        self.chk_meta.setChecked(self.config_manager.get("save_metadata", True))

        fmt = self.config_manager.get("metadata_format", "txt")
        self.cmb_meta_fmt.setCurrentIndex(0 if fmt == "txt" else 1)

        qual = self.config_manager.get("download_quality", "original")
        self.cmb_quality.setCurrentIndex(0 if qual == "original" else 1)

        # Ratings
        ratings = self.config_manager.get("default_ratings", {})
        self.chk_g.setChecked(ratings.get("g", True))
        self.chk_s.setChecked(ratings.get("s", True))
        self.chk_q.setChecked(ratings.get("q", False))
        self.chk_e.setChecked(ratings.get("e", False))
        self._update_all_checkbox_state()

        # Auth
        user = self.config_manager.get("api_username", "")
        key = self.config_manager.get("api_key", "")
        if user and key:
            self.chk_auth.setChecked(True)
            self.txt_username.setText(user)
            self.txt_api_key.setText(key)
            self.txt_username.setEnabled(True)
            self.txt_api_key.setEnabled(True)
            self.btn_save_auth.setEnabled(True)

    def _save_settings(self):
        self.config_manager.set("download_dir", self.txt_dir.text())
        self.config_manager.set("request_delay", self.slider_delay.value() / 10.0)
        self.config_manager.set("skip_existing", self.chk_skip.isChecked())
        self.config_manager.set("save_metadata", self.chk_meta.isChecked())
        self.config_manager.set("metadata_format", "txt" if self.cmb_meta_fmt.currentIndex() == 0 else "json")
        self.config_manager.set("download_quality", "original" if self.cmb_quality.currentIndex() == 0 else "large")
        self.config_manager.set("default_ratings", {
            "all": self.chk_all.isChecked(),
            "g": self.chk_g.isChecked(),
            "s": self.chk_s.isChecked(),
            "q": self.chk_q.isChecked(),
            "e": self.chk_e.isChecked()
        })

    def _on_all_ratings_toggled(self, checked: bool):
        self._updating_ratings = True
        try:
            self.chk_g.setChecked(checked)
            self.chk_s.setChecked(checked)
            self.chk_q.setChecked(checked)
            self.chk_e.setChecked(checked)
        finally:
            self._updating_ratings = False
        self._save_settings()

    def _on_individual_rating_toggled(self):
        if getattr(self, "_updating_ratings", False):
            return
        self._update_all_checkbox_state()
        self._save_settings()

    def _update_all_checkbox_state(self):
        all_checked = (
            self.chk_g.isChecked() and
            self.chk_s.isChecked() and
            self.chk_q.isChecked() and
            self.chk_e.isChecked()
        )
        self.chk_all.blockSignals(True)
        self.chk_all.setChecked(all_checked)
        self.chk_all.blockSignals(False)

    def _on_delay_changed(self, val: int):
        delay = val / 10.0
        self.lbl_delay_val.setText(f"{delay:.1f} s")
        self.api.set_delay(delay)
        self._save_settings()

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.txt_dir.text())
        if folder:
            self.txt_dir.setText(folder)
            self._save_settings()

    def _open_dir(self):
        path = self.txt_dir.text()
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.information(self, "Directory Not Found", f"Directory '{path}' does not exist yet.")

    def _toggle_auth(self, enabled: bool):
        self.txt_username.setEnabled(enabled)
        self.txt_api_key.setEnabled(enabled)
        self.btn_save_auth.setEnabled(enabled)
        if not enabled:
            self.config_manager.set("api_username", "")
            self.config_manager.set("api_key", "")
            self.api.update_credentials("", "")
            self.append_log("INFO", "Danbooru account authentication disabled.")

    def _save_auth(self):
        u = self.txt_username.text().strip()
        k = self.txt_api_key.text().strip()
        self.config_manager.set("api_username", u)
        self.config_manager.set("api_key", k)
        self.api.update_credentials(u, k)
        self.append_log("SUCCESS", "Saved Danbooru credentials.")
        QMessageBox.information(self, "Saved", "Danbooru API credentials updated.")

    def append_log(self, level: str, msg: str):
        colors = {
            "INFO": "#38bdf8",
            "SUCCESS": "#10b981",
            "WARNING": "#f59e0b",
            "ERROR": "#ef4444",
            "DEBUG": "#64748b"
        }
        color = colors.get(level, "#94a3b8")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f'<span style="color:#64748b;">[{timestamp}]</span> <b style="color:{color};">[{level}]</b> {msg}')

    # --- Fetching Posts ---
    def _start_fetch(self):
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        tags = self.tag_input.text().strip()
        ratings = []
        if not self.chk_all.isChecked():
            if self.chk_g.isChecked(): ratings.append("g")
            if self.chk_s.isChecked(): ratings.append("s")
            if self.chk_q.isChecked(): ratings.append("q")
            if self.chk_e.isChecked(): ratings.append("e")

            if not ratings:
                QMessageBox.warning(self, "No Rating Selected", "Please select at least one rating (or check 'All').")
                return

        limit = self.spin_limit.value()
        order_key = self.cmb_order.currentText().split()[0]

        self.btn_fetch.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.status_pill.setText("Fetching...")
        self.progress_bar.setValue(0)

        self.fetch_thread = QThread()
        self.fetch_worker = FetchWorker(self.api, tags, ratings, limit, order=order_key)
        self.fetch_worker.moveToThread(self.fetch_thread)

        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.log.connect(self.append_log)

        self.fetch_thread.start()

    @pyqtSlot(int, int)
    def _on_fetch_progress(self, current: int, total: int):
        pct = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_stats.setText(f"Found: {current} / {total}")

    @pyqtSlot(list)
    def _on_fetch_finished(self, posts: list):
        self.fetched_posts = posts
        self._populate_table(posts)
        self.btn_fetch.setEnabled(True)
        self.btn_download.setEnabled(len(posts) > 0)
        self.status_pill.setText(f"Fetched {len(posts)} posts")
        self.progress_bar.setValue(100 if posts else 0)

        # Cleanup thread
        if self.fetch_thread:
            self.fetch_thread.quit()
            self.fetch_thread.wait()

    @pyqtSlot(str)
    def _on_fetch_error(self, err_msg: str):
        self.btn_fetch.setEnabled(True)
        self.status_pill.setText("Error")
        QMessageBox.warning(self, "Fetch Error", f"Failed to fetch posts:\n{err_msg}")
        if self.fetch_thread:
            self.fetch_thread.quit()
            self.fetch_thread.wait()

    def _populate_table(self, posts: List[Dict[str, Any]]):
        self.table.setRowCount(0)
        self.post_row_map.clear()
        self.table.setRowCount(len(posts))

        # Update tab label
        self.table.parentWidget().parentWidget().setTabText(0, f"📋 Posts Queue ({len(posts)})")

        for row, post in enumerate(posts):
            post_id = post.get("id")
            self.post_row_map[post_id] = row

            # Row index
            item_num = QTableWidgetItem(str(row + 1))
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, item_num)

            # ID
            item_id = QTableWidgetItem(str(post_id))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_id)

            # Rating
            rating_char = (post.get("rating") or "g").lower()
            color_hex, rating_name = RATING_COLORS.get(rating_char, ("#94a3b8", "Unknown"))
            item_rating = QTableWidgetItem(f"{rating_char.upper()} ({rating_name})")
            item_rating.setForeground(QColor(color_hex))
            item_rating.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, item_rating)

            # Artist
            artist = post.get("tag_string_artist", "") or "Unknown"
            item_artist = QTableWidgetItem(artist.replace("_", " "))
            self.table.setItem(row, 3, item_artist)

            # Ext
            ext = (post.get("file_ext") or "jpg").upper()
            item_ext = QTableWidgetItem(ext)
            item_ext.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, item_ext)

            # Resolution
            w = post.get("image_width", 0)
            h = post.get("image_height", 0)
            item_res = QTableWidgetItem(f"{w}×{h}")
            item_res.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item_res)

            # Size
            size_kb = (post.get("file_size", 0) or 0) / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
            item_size = QTableWidgetItem(size_str)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, item_size)

            # Status
            item_status = QTableWidgetItem("Queued")
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 7, item_status)

        # Select first row if available
        if posts:
            self.table.selectRow(0)

    def _on_table_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self.fetched_posts):
            post = self.fetched_posts[row]
            post_id = post.get("id")
            local_path = self.downloaded_paths.get(post_id)
            self.preview_panel.set_post(post, local_path=local_path)

    def _show_table_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        if 0 <= row < len(self.fetched_posts):
            post = self.fetched_posts[row]
            menu = QMenu(self)
            menu.setStyleSheet("background-color: #131b2e; color: #f1f5f9; padding: 4px;")

            act_browser = QAction("🌐 Open in Danbooru", self)
            act_browser.triggered.connect(lambda: self.preview_panel._open_in_danbooru())
            menu.addAction(act_browser)

            act_copy_id = QAction("📋 Copy Post ID", self)
            act_copy_id.triggered.connect(lambda: self.preview_panel._copy_tags())
            menu.addAction(act_copy_id)

            post_id = post.get("id")
            local_path = self.downloaded_paths.get(post_id)
            if local_path and os.path.exists(local_path):
                act_file = QAction("📁 Open Downloaded File", self)
                act_file.triggered.connect(lambda: os.startfile(local_path))
                menu.addAction(act_file)

            menu.exec(self.table.viewport().mapToGlobal(pos))

    # --- Downloading ---
    def _start_download(self):
        if not self.fetched_posts:
            return

        self._save_settings()

        self.btn_download.setEnabled(False)
        self.btn_fetch.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.status_pill.setText("Downloading...")
        self.progress_bar.setValue(0)

        quality = "original" if self.cmb_quality.currentIndex() == 0 else "large"
        meta_fmt = "txt" if self.cmb_meta_fmt.currentIndex() == 0 else "json"

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(
            api=self.api,
            posts=self.fetched_posts,
            download_dir=self.txt_dir.text(),
            skip_existing=self.chk_skip.isChecked(),
            save_metadata=self.chk_meta.isChecked(),
            metadata_format=meta_fmt,
            quality=quality,
            delay=self.slider_delay.value() / 10.0
        )
        self.download_worker.moveToThread(self.download_thread)

        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.file_started.connect(self._on_file_started)
        self.download_worker.file_progress.connect(self._on_file_progress)
        self.download_worker.file_completed.connect(self._on_file_completed)
        self.download_worker.all_completed.connect(self._on_all_completed)
        self.download_worker.log.connect(self.append_log)

        self.download_thread.start()

    def _toggle_pause(self):
        if not self.download_worker:
            return
        if self.download_worker.is_paused:
            self.download_worker.resume()
            self.btn_pause.setText("⏸️ Pause")
            self.status_pill.setText("Downloading...")
        else:
            self.download_worker.pause()
            self.btn_pause.setText("▶️ Resume")
            self.status_pill.setText("Paused")

    def _cancel_download(self):
        if self.download_worker:
            self.download_worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.status_pill.setText("Cancelling...")

    @pyqtSlot(int, str, int, int)
    def _on_file_started(self, post_id: int, filename: str, idx: int, total: int):
        row = self.post_row_map.get(post_id)
        if row is not None:
            item = self.table.item(row, 7)
            if item:
                item.setText("⏳ Downloading...")
                item.setForeground(QColor("#38bdf8"))
            self.table.scrollToItem(self.table.item(row, 0))

        pct = int(((idx - 1) / total) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_stats.setText(f"Progress: {idx} / {total}")

    @pyqtSlot(int, int, int, float)
    def _on_file_progress(self, post_id: int, downloaded: int, total: int, speed: float):
        # Format speed
        if speed > 1024 * 1024:
            speed_str = f"{speed / (1024*1024):.2f} MB/s"
        else:
            speed_str = f"{speed / 1024:.1f} KB/s"
        self.lbl_speed.setText(f"Speed: {speed_str}")

    @pyqtSlot(int, str, str)
    def _on_file_completed(self, post_id: int, filename: str, status: str):
        row = self.post_row_map.get(post_id)
        if row is not None:
            item = self.table.item(row, 7)
            if item:
                if status == "downloaded":
                    item.setText("✓ Done")
                    item.setForeground(QColor("#10b981"))
                elif status == "skipped":
                    item.setText("⏩ Skipped")
                    item.setForeground(QColor("#f59e0b"))
                elif status == "restricted":
                    item.setText("🔒 Restricted")
                    item.setForeground(QColor("#a855f7"))
                else:
                    item.setText("❌ Failed")
                    item.setForeground(QColor("#ef4444"))

        # Save downloaded local path
        local_path = str(Path(self.txt_dir.text()) / filename)
        self.downloaded_paths[post_id] = local_path
        if self.preview_panel.current_post and self.preview_panel.current_post.get("id") == post_id:
            self.preview_panel.set_local_path(local_path)

    @pyqtSlot(dict)
    def _on_all_completed(self, summary: dict):
        self.btn_download.setEnabled(True)
        self.btn_fetch.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_pause.setText("⏸️ Pause")
        self.status_pill.setText("Completed")
        self.progress_bar.setValue(100)
        self.lbl_speed.setText("Speed: -")

        if self.download_thread:
            self.download_thread.quit()
            self.download_thread.wait()

        msg = (
            f"Download Batch Completed!\n\n"
            f"• Downloaded: {summary.get('downloaded', 0)}\n"
            f"• Skipped (Already existed): {summary.get('skipped', 0)}\n"
            f"• Failed / Restricted: {summary.get('failed', 0)}\n"
            f"• Total Processed: {summary.get('total', 0)}"
        )
        QMessageBox.information(self, "Download Complete", msg)

    def closeEvent(self, event):
        # Gracefully handle window close
        if self.download_worker:
            self.download_worker.cancel()
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.quit()
            self.download_thread.wait(1000)
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.fetch_thread.quit()
            self.fetch_thread.wait(1000)
        if hasattr(self, "tag_input"):
            self.tag_input.cleanup()
        if hasattr(self, "preview_panel"):
            self.preview_panel.cleanup()
        event.accept()
