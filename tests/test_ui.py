import os
import unittest

# Ensure PyQt runs headlessly in offscreen mode
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow
from ui.widgets import RatingBadge, TagAutoCompleteLineEdit
from ui.preview_panel import PreviewPanel
from core.api import DanbooruAPI


class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create single QApplication instance for all UI tests
        cls.app = QApplication.instance() or QApplication([])

    def test_rating_badge(self):
        """Test RatingBadge color and text generation."""
        badge_g = RatingBadge("g")
        badge_e = RatingBadge("e")
        self.assertIsNotNone(badge_g)
        self.assertIsNotNone(badge_e)

    def test_main_window_init(self):
        """Test MainWindow window title and initial states."""
        win = MainWindow()
        self.assertEqual(win.windowTitle(), "DanbuDL: Danbooru Downloader")
        self.assertIsNotNone(win.table)
        self.assertIsNotNone(win.preview_panel)
        self.assertFalse(win.btn_download.isEnabled())
        win.close()

    def test_rating_all_bidirectional_sync(self):
        """Test All rating checkbox synchronization with individual checkboxes."""
        win = MainWindow()

        # Turn ON All
        win.chk_all.setChecked(True)
        self.assertTrue(win.chk_g.isChecked())
        self.assertTrue(win.chk_s.isChecked())
        self.assertTrue(win.chk_q.isChecked())
        self.assertTrue(win.chk_e.isChecked())

        # Uncheck one rating (Explicit)
        win.chk_e.setChecked(False)
        self.assertFalse(win.chk_all.isChecked())

        # Re-check Explicit -> All should automatically become checked
        win.chk_e.setChecked(True)
        self.assertTrue(win.chk_all.isChecked())

        # Turn OFF All
        win.chk_all.setChecked(False)
        self.assertFalse(win.chk_g.isChecked())
        self.assertFalse(win.chk_s.isChecked())
        self.assertFalse(win.chk_q.isChecked())
        self.assertFalse(win.chk_e.isChecked())

        win.close()

    def test_table_population_and_preview_selection(self):
        """Test populating table with mock posts and updating preview on selection."""
        win = MainWindow()
        mock_posts = [
            {
                "id": 1111,
                "rating": "s",
                "tag_string_artist": "test_illustrator",
                "file_ext": "png",
                "image_width": 1920,
                "image_height": 1080,
                "file_size": 204800,
                "score": 99,
                "tag_string": "1girl solo blue_hair"
            },
            {
                "id": 2222,
                "rating": "g",
                "tag_string_artist": "another_artist",
                "file_ext": "jpg",
                "image_width": 800,
                "image_height": 600,
                "file_size": 102400,
                "score": 15,
                "tag_string": "scenery outdoors"
            }
        ]

        win.fetched_posts = mock_posts
        win._populate_table(mock_posts)

        self.assertEqual(win.table.rowCount(), 2)
        self.assertEqual(win.table.item(0, 1).text(), "1111")
        self.assertEqual(win.table.item(1, 1).text(), "2222")

        # Select row 0
        win.table.selectRow(0)
        self.assertIsNotNone(win.preview_panel.current_post)
        self.assertEqual(win.preview_panel.current_post["id"], 1111)
        self.assertEqual(win.preview_panel.id_lbl.text(), "1111")

        win.close()

    def test_clean_close_event(self):
        """Test that closing MainWindow stops all threads cleanly without crashes."""
        win = MainWindow()
        win.show()
        # Trigger closeEvent
        win.close()
        self.app.processEvents()
        # If no QThread Destroyed assertion failed, test passes


if __name__ == "__main__":
    unittest.main()
