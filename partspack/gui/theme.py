# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# MS-Office blue-ribbon app theme

from PySide6.QtGui import QColor, QPalette

from .icons import spin_arrow_png, check_png

OFFICE = {
    "text":    "#1e1e1e",
    "muted":   "#5a6472",
    "accent":  "#2b579a",
    "green":   "#1e7c2f",
    "sel":     "#fdf4bf",
    "sel_bd":  "#e5c365",
    "g_window":  "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #eaeef5, "
                 "stop:1 #d6deea)",
    "g_ribbon":  "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f6f9fd, "
                 "stop:1 #dde6f2)",
    "g_btn":     "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fdfefe, "
                 "stop:0.5 #f0f4fa, stop:0.5 #e6edf6, stop:1 #f3f7fc)",
    "g_rest":    "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fdfeff, "
                 "stop:1 #eef2f9)",
    "rest_bd":   "#d3dcea",
    "g_hover":   "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #fdfcf6, "
                 "stop:0.5 #fdf4cf, stop:0.5 #ffec9d, stop:1 #ffe78e)",
    "g_press":   "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f5c97a, "
                 "stop:0.5 #f3b54f, stop:0.5 #f5a838, stop:1 #fbd089)",
    "g_check":   "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffe7a6, "
                 "stop:0.5 #ffd773, stop:0.5 #ffcf57, stop:1 #ffe39a)",
    "g_default": "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5d8fd4, "
                 "stop:0.5 #386bb0, stop:0.5 #2b579a, stop:1 #4377bf)",
    "g_default_h": "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #6fa0e0, "
                   "stop:0.5 #4378bd, stop:0.5 #3463a9, stop:1 #5286cf)",
    "g_head":    "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #eef2f8, "
                 "stop:1 #d4deec)",
    "border":    "#a3b4cc",
    "border_lt": "#c3cfe0",
    "surface":   "#ffffff",
    "alt":       "#eef3fa",
}

# per-step ribbon tints blue to green, indexed step-1, saturates at last
STEP_TINTS = [
    "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f4f8ff, stop:1 #e6eefb)",
    "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #eef8f3, stop:1 #dfeee7)",
    "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ebf7ec, stop:1 #dbecdf)",
]

_QSS_TMPL = """
QMainWindow, QDialog {{ background:{g_window}; color:{text}; }}
QToolTip {{ background:#fffdf5; color:{text}; border:1px solid {border};
           padding:3px 6px; }}

QToolBar {{ background:{g_ribbon}; border:0px;
           border-bottom:1px solid {border}; spacing:1px; padding:3px; }}
QToolBar::separator {{ background:{border_lt}; width:1px; margin:4px 4px; }}
QToolButton {{ background:{g_rest}; border:1px solid {rest_bd};
              border-radius:4px; padding:3px 4px; margin:1px; color:{text}; }}
QToolButton:hover {{ background:{g_hover}; border:1px solid {sel_bd}; }}
QToolButton:pressed {{ background:{g_press}; border:1px solid #d18b27; }}
QToolButton:checked {{ background:{g_check}; border:1px solid #e0a93a; }}
QToolButton:checked:hover {{ background:{g_hover}; border:1px solid {sel_bd}; }}
QToolButton#generate_btn {{ color:#ffffff; font-weight:bold;
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #34a853,
    stop:0.5 #2a9047, stop:0.5 #1e7c2f, stop:1 #36a457);
    border:1px solid #17661f; }}
QToolButton#generate_btn:hover {{ background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #43bd63, stop:0.5 #34a050, stop:0.5 #258c37, stop:1 #45b566);
    border:1px solid #145a1b; }}
QToolButton#generate_btn:pressed {{ background:qlineargradient(x1:0,y1:0,x2:0,
    y2:1, stop:0 #1e7c2f, stop:1 #2a9047); border:1px solid #114d17; }}
QToolButton#generate_btn:disabled {{ color:#eef3ee;
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #9bc6a6,
    stop:1 #8bbb97); border:1px solid #7da888; }}

QPushButton {{ background:{g_btn}; border:1px solid {border}; border-radius:5px;
              padding:5px 18px; color:{text}; font-weight:bold; }}
QPushButton:hover {{ background:{g_hover}; border-color:{sel_bd}; }}
QPushButton:pressed {{ background:{g_press}; border-color:#d18b27; }}
QPushButton:disabled {{ color:{muted}; background:#e8ecf2;
                       border-color:{border_lt}; }}
QPushButton:default {{ background:{g_default}; color:#ffffff;
                      border:1px solid #244c84; }}
QPushButton:default:hover {{ background:{g_default_h}; border-color:#1f4374; }}

QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QAbstractSpinBox {{
    background:{surface}; border:1px solid {border}; border-radius:4px;
    padding:2px 5px; color:{text}; selection-background-color:{accent};
    selection-color:#ffffff; }}
QComboBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {{
    border:1px solid #5b8fd6; }}
QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus,
QSpinBox:focus, QAbstractSpinBox:focus {{ border:1px solid {accent}; }}
QComboBox::drop-down {{ border:0px; width:18px; }}
QComboBox QAbstractItemView {{ background:{surface}; border:1px solid {border};
    selection-background-color:{sel}; selection-color:{text}; outline:0; }}

QAbstractSpinBox {{ padding-right:18px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin:border; subcontrol-position:top right; width:16px;
    background:{g_btn}; border-left:1px solid {border};
    border-bottom:1px solid {border_lt}; border-top-right-radius:4px; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin:border; subcontrol-position:bottom right; width:16px;
    background:{g_btn}; border-left:1px solid {border};
    border-bottom-right-radius:4px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background:{g_hover}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image:url({arrow_up}); width:9px; height:9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image:url({arrow_dn}); width:9px; height:9px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{
    image:url({arrow_up_dis}); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    image:url({arrow_dn_dis}); }}
QCheckBox, QLabel, QRadioButton {{ background:transparent; color:{text}; }}
QCheckBox {{ spacing:6px; }}
QCheckBox::indicator {{ width:16px; height:16px; border:1px solid {border};
    border-radius:3px; background:{surface}; }}
QCheckBox::indicator:hover {{ border:1px solid #5b8fd6; }}
QCheckBox::indicator:checked {{ background:{g_default}; border:1px solid #244c84;
    image:url({check_img}); }}
QCheckBox::indicator:checked:hover {{ border:1px solid #1f4374; }}
QCheckBox::indicator:disabled {{ background:#e8ecf2; border-color:{border_lt}; }}

QGroupBox {{ border:1px solid {border_lt}; border-radius:5px; margin-top:8px;
    padding:6px 4px 4px 4px; }}
QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px;
    color:{muted}; font-weight:bold; }}

QMenu {{ background:#fbfcfe; border:1px solid {border}; padding:3px; }}
QMenu::item {{ padding:5px 26px 5px 22px; border-radius:4px; color:{text}; }}
QMenu::item:selected {{ background:{g_hover}; border:1px solid {sel_bd};
    color:{text}; }}
QMenu::separator {{ height:1px; background:{border_lt}; margin:4px 8px; }}

QDockWidget {{ titlebar-close-icon:none; color:{text}; }}
QDockWidget::title {{ background:{g_head}; padding:5px 8px; color:{muted};
    border-bottom:1px solid {border}; font-weight:bold; }}

QTableWidget, QTableView, QListWidget, QTreeView {{ background:{surface};
    alternate-background-color:{alt}; border:1px solid {border};
    gridline-color:{border_lt}; outline:0;
    selection-background-color:{sel}; selection-color:{text}; }}
QHeaderView::section {{ background:{g_head}; color:{muted}; padding:5px 6px;
    border:0px; border-right:1px solid {border_lt};
    border-bottom:1px solid {border}; font-weight:bold; }}
QTabWidget::pane {{ border:1px solid {border}; border-radius:4px; top:-1px; }}
QTabBar::tab {{ background:{g_rest}; border:1px solid {rest_bd};
    border-bottom:0px; border-top-left-radius:4px; border-top-right-radius:4px;
    padding:5px 12px; margin-right:2px; color:{muted}; }}
QTabBar::tab:selected {{ background:{g_ribbon}; color:{text}; }}

QStatusBar {{ background:{g_ribbon}; color:{muted};
    border-top:1px solid {border}; }}
QStatusBar::item {{ border:0px; }}
QScrollBar:vertical {{ background:#dde4ee; width:13px; margin:0; }}
QScrollBar::handle:vertical {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #b6c4da, stop:1 #93a7c6); border:1px solid #8295b3;
    border-radius:5px; min-height:24px; margin:2px; }}
QScrollBar:horizontal {{ background:#dde4ee; height:13px; margin:0; }}
QScrollBar::handle:horizontal {{ background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #b6c4da, stop:1 #93a7c6); border:1px solid #8295b3;
    border-radius:5px; min-width:24px; margin:2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
"""


def office_qss():
    return _QSS_TMPL.format(
        arrow_up=spin_arrow_png("up", OFFICE["accent"]),
        arrow_dn=spin_arrow_png("down", OFFICE["accent"]),
        arrow_up_dis=spin_arrow_png("up", OFFICE["muted"]),
        arrow_dn_dis=spin_arrow_png("down", OFFICE["muted"]),
        check_img=check_png("#ffffff"),
        **OFFICE)


def apply_office_theme(app):
    """Apply light MS-Office theme."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#e2e8f2"))
    pal.setColor(QPalette.WindowText, QColor(OFFICE["text"]))
    pal.setColor(QPalette.Base, QColor(OFFICE["surface"]))
    pal.setColor(QPalette.AlternateBase, QColor(OFFICE["alt"]))
    pal.setColor(QPalette.Text, QColor(OFFICE["text"]))
    pal.setColor(QPalette.Button, QColor("#e8eef6"))
    pal.setColor(QPalette.ButtonText, QColor(OFFICE["text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(OFFICE["surface"]))
    pal.setColor(QPalette.ToolTipText, QColor(OFFICE["text"]))
    pal.setColor(QPalette.Highlight, QColor(OFFICE["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(OFFICE["muted"]))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(OFFICE["muted"]))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(OFFICE["muted"]))
    app.setPalette(pal)
    app.setStyleSheet(office_qss())
