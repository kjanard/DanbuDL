import os
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QPixmap, QImage
from ui.widgets import RatingBadge, CATEGORY_COLORS


class PreviewLoader(QObject):
    """Background loader for preview images to prevent UI lag."""
    loaded = pyqtSignal(int, bytes)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def fetch(self, post_id: int, url: str):
        if not url:
            return
        data = self.api.get_preview_image(url)
        if data:
            self.loaded.emit(post_id, data)


class PreviewPanel(QWidget):
    """Side panel displaying post preview image, metadata, tags, and action buttons."""
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.current_post: Optional[Dict[str, Any]] = None
        self.current_pixmap: Optional[QPixmap] = None
        self.downloaded_filepath: Optional[str] = None

        # Thread for preview loading
        self.thread = QThread()
        self.loader = PreviewLoader(self.api)
        self.loader.moveToThread(self.thread)
        self.loader.loaded.connect(self._on_image_loaded)
        self.thread.start()

        from PyQt6.QtCore import QCoreApplication
        app_inst = QCoreApplication.instance()
        if app_inst:
            app_inst.aboutToQuit.connect(self.cleanup)

        self._init_ui()

    def cleanup(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(500)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header Title
        title_box = QHBoxLayout()
        self.title_lbl = QLabel("Post Details")
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        title_box.addWidget(self.title_lbl)
        title_box.addStretch()

        self.rating_container = QHBoxLayout()
        title_box.addLayout(self.rating_container)
        layout.addLayout(title_box)

        # Image Preview Box
        self.image_container = QFrame()
        self.image_container.setStyleSheet("""
            QFrame {
                background-color: #080c14;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        img_layout = QVBoxLayout(self.image_container)
        img_layout.setContentsMargins(4, 4, 4, 4)

        self.image_lbl = QLabel("No image selected")
        self.image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_lbl.setStyleSheet("color: #64748b; font-size: 13px;")
        self.image_lbl.setMinimumHeight(240)
        img_layout.addWidget(self.image_lbl)
        layout.addWidget(self.image_container)

        # Details Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.meta_layout = QVBoxLayout(scroll_content)
        self.meta_layout.setContentsMargins(2, 4, 2, 4)
        self.meta_layout.setSpacing(6)

        # Metadata labels
        self.id_lbl = self._create_info_row("ID:", "-")
        self.artist_lbl = self._create_info_row("Artist:", "-")
        self.character_lbl = self._create_info_row("Character:", "-")
        self.copyright_lbl = self._create_info_row("Copyright:", "-")
        self.dims_lbl = self._create_info_row("Resolution:", "-")
        self.score_lbl = self._create_info_row("Score:", "-")

        # Tags label & text area
        tags_header = QLabel("Tags:")
        tags_header.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 12px; margin-top: 6px;")
        self.meta_layout.addWidget(tags_header)

        self.tags_lbl = QLabel("None")
        self.tags_lbl.setWordWrap(True)
        self.tags_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        self.tags_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.meta_layout.addWidget(self.tags_lbl)
        self.meta_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Action Buttons
        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        self.btn_danbooru = QPushButton("🌐 View on Danbooru")
        self.btn_danbooru.clicked.connect(self._open_in_danbooru)
        self.btn_danbooru.setEnabled(False)
        btn_box.addWidget(self.btn_danbooru)

        self.btn_copy_tags = QPushButton("📋 Copy Tags to Clipboard")
        self.btn_copy_tags.clicked.connect(self._copy_tags)
        self.btn_copy_tags.setEnabled(False)
        btn_box.addWidget(self.btn_copy_tags)

        self.btn_open_file = QPushButton("📁 Open Local File")
        self.btn_open_file.clicked.connect(self._open_local_file)
        self.btn_open_file.setEnabled(False)
        btn_box.addWidget(self.btn_open_file)

        layout.addLayout(btn_box)

    def _create_info_row(self, label_text: str, val_text: str):
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #94a3b8; font-weight: 600; min-width: 75px;")
        val = QLabel(val_text)
        val.setStyleSheet("color: #f1f5f9;")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(lbl)
        row.addWidget(val, 1)
        self.meta_layout.addLayout(row)
        return val

    def set_post(self, post: Dict[str, Any], local_path: Optional[str] = None):
        self.current_post = post
        self.downloaded_filepath = local_path

        post_id = post.get("id")
        self.title_lbl.setText(f"Post #{post_id}")
        self.id_lbl.setText(str(post_id))

        # Rating badge
        while self.rating_container.count():
            item = self.rating_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rating = post.get("rating", "g")
        badge = RatingBadge(rating)
        self.rating_container.addWidget(badge)

        # Meta fields
        artist = post.get("tag_string_artist", "") or "Unknown"
        char = post.get("tag_string_character", "") or "-"
        copy = post.get("tag_string_copyright", "") or "-"
        w = post.get("image_width", 0)
        h = post.get("image_height", 0)
        ext = post.get("file_ext", "").upper()
        score = post.get("score", 0)
        size_kb = (post.get("file_size", 0) or 0) / 1024

        self.artist_lbl.setText(artist.replace("_", " "))
        self.character_lbl.setText(char.replace("_", " ") if char != "-" else "-")
        self.copyright_lbl.setText(copy.replace("_", " ") if copy != "-" else "-")
        self.dims_lbl.setText(f"{w} × {h} ({ext}, {size_kb:.1f} KB)")
        self.score_lbl.setText(f"{score}")

        tags = post.get("tag_string", "").replace("_", " ")
        self.tags_lbl.setText(tags)

        self.btn_danbooru.setEnabled(True)
        self.btn_copy_tags.setEnabled(True)

        if local_path and Path(local_path).exists():
            self.btn_open_file.setEnabled(True)
        else:
            self.btn_open_file.setEnabled(False)

        # Load image preview
        self.image_lbl.setText("Loading preview...")
        # Prefer preview_file_url for speed, or large_file_url
        img_url = post.get("preview_file_url") or post.get("large_file_url")
        if img_url:
            self.loader.fetch(post_id, img_url)
        else:
            self.image_lbl.setText("No preview available")

    def _on_image_loaded(self, post_id: int, image_bytes: bytes):
        if not self.current_post or self.current_post.get("id") != post_id:
            return

        pix = QPixmap()
        pix.loadFromData(image_bytes)
        if not pix.isNull():
            self.current_pixmap = pix
            scaled = pix.scaled(
                self.image_container.width() - 8,
                240,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_lbl.setPixmap(scaled)
        else:
            self.image_lbl.setText("Failed to decode image")

    def set_local_path(self, path: str):
        self.downloaded_filepath = path
        if path and Path(path).exists():
            self.btn_open_file.setEnabled(True)
            # If local file exists, display full local image!
            pix = QPixmap(path)
            if not pix.isNull():
                self.current_pixmap = pix
                scaled = pix.scaled(
                    self.image_container.width() - 8,
                    240,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_lbl.setPixmap(scaled)

    def _open_in_danbooru(self):
        if self.current_post:
            url = f"https://danbooru.donmai.us/posts/{self.current_post.get('id')}"
            webbrowser.open(url)

    def _copy_tags(self):
        if self.current_post:
            tags = self.current_post.get("tag_string", "")
            QApplication.clipboard().setText(tags)
            self.btn_copy_tags.setText("✓ Copied!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy_tags.setText("📋 Copy Tags to Clipboard"))

    def _open_local_file(self):
        if self.downloaded_filepath and os.path.exists(self.downloaded_filepath):
            os.startfile(self.downloaded_filepath)
