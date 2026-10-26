"""全局主题：颜色常量 + QSS 样式表（现代 B 端风格，克制配色）。"""

PRIMARY = "#3b82f6"
PRIMARY_DARK = "#2563eb"
PRIMARY_LIGHT = "#eff6ff"
SUCCESS = "#16a34a"
WARNING = "#d97706"
DANGER = "#dc2626"

BG = "#f4f6fa"
CARD = "#ffffff"
BORDER = "#e2e8f0"
TEXT = "#1e293b"
TEXT_SUB = "#64748b"
SIDEBAR_BG = "#0f172a"
SIDEBAR_TEXT = "#94a3b8"
SIDEBAR_ACTIVE = "#1e293b"


def app_qss() -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#sidebar {{
    background: {SIDEBAR_BG};
    border: none;
}}
QLabel#appTitle {{
    color: #ffffff; font-size: 15px; font-weight: bold; background: transparent;
}}
QLabel#appSub {{
    color: {SIDEBAR_TEXT}; font-size: 11px; background: transparent;
}}
QPushButton#navBtn {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    color: {SIDEBAR_TEXT}; background: transparent; font-size: 13px;
}}
QPushButton#navBtn:hover {{ background: #1e293b; color: #e2e8f0; }}
QPushButton#navBtn:checked {{
    background: {PRIMARY}; color: #ffffff; font-weight: bold;
}}
QLabel#pageTitle {{ font-size: 20px; font-weight: bold; color: {TEXT}; }}
QLabel#pageDesc  {{ font-size: 12px; color: {TEXT_SUB}; }}

QFrame#card, QGroupBox#card {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
}}
QLabel#cardTitle {{ font-size: 14px; font-weight: bold; color: {TEXT}; border: none; }}
QLabel#hint {{ color: {TEXT_SUB}; font-size: 12px; }}

QPushButton {{
    background: #ffffff; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 14px; color: {TEXT};
}}
QPushButton:hover {{ border-color: {PRIMARY}; color: {PRIMARY_DARK}; }}
QPushButton:disabled {{ color: #a8b3c5; background: #f1f5f9; }}
QPushButton#primaryBtn {{
    background: {PRIMARY}; border: none; color: white; font-weight: bold; padding: 7px 18px;
}}
QPushButton#primaryBtn:hover {{ background: {PRIMARY_DARK}; }}
QPushButton#primaryBtn:disabled {{ background: #93c5fd; color: #f8fafc; }}
QPushButton#dangerBtn {{ color: {DANGER}; }}
QPushButton#dangerBtn:hover {{ border-color: {DANGER}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: #ffffff; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: white; border: 1px solid {BORDER}; selection-background-color: {PRIMARY_LIGHT};
    selection-color: {PRIMARY_DARK};
}}

QTableWidget {{
    background: white; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: #eef2f7;
    alternate-background-color: #f8fafc;
}}
QTableWidget::item {{ padding: 4px 6px; }}
QTableWidget::item:selected {{ background: {PRIMARY_LIGHT}; color: {PRIMARY_DARK}; }}
QHeaderView::section {{
    background: #f8fafc; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-weight: bold; color: {TEXT_SUB};
}}

QTreeWidget {{
    background: white; border: 1px solid {BORDER}; border-radius: 8px;
    alternate-background-color: #f8fafc;
}}
QTreeWidget::item:selected {{ background: {PRIMARY_LIGHT}; color: {PRIMARY_DARK}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: white; }}
QTabBar::tab {{
    background: transparent; padding: 7px 16px; color: {TEXT_SUB};
    border: none; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {PRIMARY_DARK}; border-bottom: 2px solid {PRIMARY}; font-weight: bold; }}

QProgressBar {{
    background: #eef2f7; border: none; border-radius: 5px; height: 10px; text-align: center;
    color: {TEXT_SUB}; font-size: 10px;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 5px; }}

QStatusBar {{ background: transparent; color: {TEXT_SUB}; }}
QSplitter::handle {{ background: transparent; }}
QCheckBox {{ spacing: 6px; }}
QScrollBar:vertical {{
    background: transparent; width: 9px; margin: 2px;
}}
QScrollBar::handle:vertical {{ background: #cbd5e1; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background: {SIDEBAR_BG}; color: #e2e8f0; border: none; padding: 5px 8px; border-radius: 4px;
}}
"""
