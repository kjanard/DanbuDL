import time
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QObject, QThread
from PyQt6.QtGui import QColor, QFont, QKeyEvent

CATEGORY_COLORS = {
    0: ("#38bdf8", "General"),      # Blue/Cyan
    1: ("#f59e0b", "Artist"),       # Orange
    3: ("#c084fc", "Copyright"),    # Purple
    4: ("#34d399", "Character"),    # Emerald
    5: ("#94a3b8", "Meta")          # Slate
}

RATING_COLORS = {
    "g": ("#10b981", "General"),
    "s": ("#06b6d4", "Sensitive"),
    "q": ("#f59e0b", "Questionable"),
    "e": ("#ef4444", "Explicit")
}


class AutocompleteWorker(QObject):
    """Background worker to fetch autocomplete tags without freezing the GUI."""
    results_ready = pyqtSignal(str, list)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def fetch(self, query: str):
        try:
            results = self.api.get_autocomplete(query, limit=10)
            self.results_ready.emit(query, results)
        except Exception:
            self.results_ready.emit(query, [])


class TagAutoCompleteLineEdit(QLineEdit):
    """
    Intelligent Tag Input with Danbooru API autocomplete, category color coding,
    and cursor word replacement.
    """
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api

        # Debounce timer (450ms polite pacing to prevent API throttling)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(450)
        self.timer.timeout.connect(self._request_suggestions)

        self.textChanged.connect(self._on_text_changed)
        self.cache: Dict[str, list] = {}

        # Popup list for suggestions
        self.popup = QListWidget()
        self.popup.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.setStyleSheet("""
            QListWidget {
                background-color: #131b2e;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #f1f5f9;
                font-size: 13px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #1e293b;
                color: #38bdf8;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
        """)
        self.popup.itemClicked.connect(self._insert_selected_tag)

        # Autocomplete worker thread
        self.thread = QThread()
        self.worker = AutocompleteWorker(self.api)
        self.worker.moveToThread(self.thread)
        self.worker.results_ready.connect(self._display_suggestions)
        self.thread.start()

        from PyQt6.QtCore import QCoreApplication
        app_inst = QCoreApplication.instance()
        if app_inst:
            app_inst.aboutToQuit.connect(self.cleanup)

        self.current_word = ""
        self.word_start = 0
        self.word_end = 0

    def cleanup(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(500)

    def _on_text_changed(self):
        text = self.text()
        cursor_pos = self.cursorPosition()

        # Find word under cursor
        before = text[:cursor_pos]
        after = text[cursor_pos:]

        start = before.rfind(" ") + 1
        end_rel = after.find(" ")
        end = cursor_pos + (end_rel if end_rel != -1 else len(after))

        word = text[start:end].strip()
        self.current_word = word
        self.word_start = start
        self.word_end = end

        if len(word) >= 2 and not word.startswith("rating:") and not word.startswith("order:"):
            self.timer.start()
        else:
            self.popup.hide()

    def _request_suggestions(self):
        query = self.current_word.lower()
        if query and len(query) >= 2:
            if query in self.cache:
                self._display_suggestions(self.current_word, self.cache[query])
                return
            # Trigger worker in thread
            QTimer.singleShot(0, lambda: self.worker.fetch(self.current_word))

    def _display_suggestions(self, query: str, suggestions: list):
        if suggestions:
            self.cache[query.lower()] = suggestions

        if query != self.current_word or not suggestions:
            self.popup.hide()
            return

        self.popup.clear()
        for item in suggestions:
            val = item.get("value", "")
            count = item.get("post_count", 0)
            cat = item.get("category", 0)
            color_hex, cat_name = CATEGORY_COLORS.get(cat, ("#94a3b8", "Tag"))

            # Format item
            formatted_count = f"{count:,}" if count else ""
            display_text = f"{val.replace('_', ' ')}  ({formatted_count}) [{cat_name}]"

            list_item = QListWidgetItem(display_text)
            list_item.setForeground(QColor(color_hex))
            list_item.setData(Qt.ItemDataRole.UserRole, val)
            self.popup.addItem(list_item)

        # Position popup directly below input box
        line_rect = self.rect()
        pos = self.mapToGlobal(QPoint(0, line_rect.bottom() + 4))
        self.popup.setFixedWidth(max(self.width(), 320))
        self.popup.setFixedHeight(min(240, max(60, len(suggestions) * 32 + 10)))
        self.popup.move(pos)
        self.popup.show()

    def _insert_selected_tag(self, item: QListWidgetItem):
        tag_value = item.data(Qt.ItemDataRole.UserRole)
        if not tag_value:
            return

        text = self.text()
        # Replace the word at [word_start:word_end]
        new_text = text[:self.word_start] + tag_value + " " + text[self.word_end:].lstrip()
        self.setText(new_text)
        new_cursor = self.word_start + len(tag_value) + 1
        self.setCursorPosition(new_cursor)
        self.popup.hide()

    def keyPressEvent(self, event: QKeyEvent):
        if self.popup.isVisible():
            if event.key() == Qt.Key.Key_Down:
                cur = self.popup.currentRow()
                self.popup.setCurrentRow(cur + 1 if cur < self.popup.count() - 1 else 0)
                return
            elif event.key() == Qt.Key.Key_Up:
                cur = self.popup.currentRow()
                self.popup.setCurrentRow(cur - 1 if cur > 0 else self.popup.count() - 1)
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                cur_item = self.popup.currentItem()
                if cur_item:
                    self._insert_selected_tag(cur_item)
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self.popup.hide()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # Hide popup when focus leaves
        QTimer.singleShot(150, self.popup.hide)
        super().focusOutEvent(event)


class RatingBadge(QFrame):
    """Colored badge widget displaying post rating."""
    def __init__(self, rating: str, parent=None):
        super().__init__(parent)
        color_hex, label_text = RATING_COLORS.get(rating.lower(), ("#94a3b8", "Unknown"))
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color_hex}22;
                border: 1px solid {color_hex}77;
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QLabel {{
                color: {color_hex};
                font-weight: 600;
                font-size: 11px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        lbl = QLabel(f"{label_text.upper()} ({rating.upper()})")
        layout.addWidget(lbl)
