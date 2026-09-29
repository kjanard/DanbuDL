"""
Modern Dark Theme QSS stylesheet for Danbooru Downloader
"""
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CHECK_ICON = str(ASSETS_DIR / "check.svg").replace("\\", "/")

DARK_THEME_QSS = """
/* Base Window & Global */
QMainWindow, QDialog {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e2e8f0;
    outline: none;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 25px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0f172a;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 25px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #475569;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* GroupBox / Card Containers */
QGroupBox {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    font-size: 13px;
    color: #94a3b8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: #131b2e;
    color: #38bdf8;
}

/* Inputs & Edits */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 6px 12px;
    color: #f8fafc;
    font-size: 13px;
    selection-background-color: #38bdf8;
    selection-color: #0f172a;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
    background-color: #141f36;
}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

/* ComboBox Dropdown */
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #131b2e;
    border: 1px solid #334155;
    border-radius: 6px;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
    padding: 4px;
}

/* Buttons */
QPushButton {
    background-color: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #2e3d59;
    border-color: #475569;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #182234;
}
QPushButton:disabled {
    background-color: #111827;
    color: #4b5563;
    border-color: #1f2937;
}

/* Primary Button (Neon Cyan) */
QPushButton#primaryBtn {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryBtn:hover {
    background-color: #0369a1;
    border-color: #7dd3fc;
}
QPushButton#primaryBtn:pressed {
    background-color: #075985;
}

/* Success Button (Emerald) */
QPushButton#successBtn {
    background-color: #059669;
    border: 1px solid #10b981;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#successBtn:hover {
    background-color: #047857;
    border-color: #34d399;
}
QPushButton#successBtn:pressed {
    background-color: #065f46;
}

/* Danger Button (Red) */
QPushButton#dangerBtn {
    background-color: #dc2626;
    border: 1px solid #ef4444;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#dangerBtn:hover {
    background-color: #b91c1c;
    border-color: #f87171;
}

/* Secondary Button */
QPushButton#secondaryBtn {
    background-color: #334155;
    border: 1px solid #475569;
}
QPushButton#secondaryBtn:hover {
    background-color: #475569;
}

/* CheckBoxes */
QCheckBox {
    spacing: 8px;
    font-size: 13px;
    color: #cbd5e1;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #0f172a;
}
QCheckBox::indicator:hover {
    border-color: #38bdf8;
}
QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
    image: url("__CHECK_ICON__");
    padding: 2px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1e293b;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #0284c7;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #38bdf8;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #7dd3fc;
}

/* Progress Bar */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 7px;
    text-align: center;
    color: #f8fafc;
    font-weight: 600;
    font-size: 12px;
    height: 20px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 6px;
}

/* Table View */
QTableWidget {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    gridline-color: #1e293b;
    color: #e2e8f0;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
}
QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #172033;
}
QTableWidget::item:selected {
    background-color: #1a253c;
    color: #38bdf8;
}
QHeaderView::section {
    background-color: #131b2e;
    color: #94a3b8;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #1e293b;
    font-weight: 600;
    font-size: 12px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #1e293b;
    border-radius: 8px;
    background-color: #131b2e;
    top: -1px;
}
QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #1e293b;
    border-bottom: none;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #131b2e;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}
QTabBar::tab:hover:!selected {
    background-color: #182236;
    color: #f1f5f9;
}

/* Text Edit / Logs */
QTextEdit, QPlainTextEdit {
    background-color: #080c14;
    border: 1px solid #1e293b;
    border-radius: 7px;
    color: #94a3b8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
}

/* Tooltip */
QToolTip {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* Status Bar */
QStatusBar {
    background-color: #0b0f19;
    border-top: 1px solid #1e293b;
    color: #94a3b8;
    font-size: 12px;
}
""".replace("__CHECK_ICON__", CHECK_ICON)

