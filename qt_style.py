"""Qt parts of Anki: pop-up menus, list and text boxes in every dialog, the
Browser's table and sidebar, the card preview's button bar, the card template
editor, and default buttons in the Add and Preferences windows.

Controls such as buttons, pop-up buttons and checkboxes are left to the
native macOS style, which already draws them as Tahoe controls. These rules
only cover what Anki draws itself or styles flatly: menus get rounded corners,
an inset accent highlight and inset separators; the Browser table loses its
grid and boxed header; the sidebar reads like a source list.
"""

from __future__ import annotations

from typing import Callable

from aqt import gui_hooks
from aqt.qt import QApplication, QMenu, QPushButton, Qt

ROUNDED = "mnRounded"
MARK = "/* macos-native */"


def _palette(dark: bool) -> dict:
    if dark:
        return {
            "menu": "#2b2b2d", "border": "rgba(255, 255, 255, 0.14)", "fg": "rgba(255, 255, 255, 0.88)",
            "secondary": "rgba(255, 255, 255, 0.55)", "disabled": "rgba(255, 255, 255, 0.3)",
            "sep": "rgba(255, 255, 255, 0.12)", "hover": "rgba(255, 255, 255, 0.07)",
            "sidebar": "#262628", "alt": "rgba(255, 255, 255, 0.035)", "inactive": "rgba(255, 255, 255, 0.14)",
        }
    return {
        "menu": "#f6f6f6", "border": "rgba(0, 0, 0, 0.14)", "fg": "rgba(0, 0, 0, 0.86)",
        "secondary": "rgba(0, 0, 0, 0.5)", "disabled": "rgba(0, 0, 0, 0.28)",
        "sep": "rgba(0, 0, 0, 0.1)", "hover": "rgba(0, 0, 0, 0.05)",
        "sidebar": "#f0f0f2", "alt": "rgba(0, 0, 0, 0.025)", "inactive": "rgba(0, 0, 0, 0.1)",
    }


def stylesheet(dark: bool, accent: str) -> str:
    p = _palette(dark)
    return f"""
{MARK}
QMenu {{
    background-color: {p["menu"]};
    border: 1px solid {p["border"]};
    padding: 5px;
}}
QMenu[{ROUNDED}="true"] {{
    border-radius: 10px;
}}
QMenu::item {{
    color: {p["fg"]};
    background: transparent;
    padding: 4px 22px 4px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    color: #ffffff;
    background-color: {accent};
}}
QMenu::item:disabled {{
    color: {p["disabled"]};
    background: transparent;
}}
QMenu::separator {{
    height: 1px;
    background: {p["sep"]};
    margin: 5px 10px;
}}

QListView, QTreeView, QTableView {{
    background: palette(base);
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QListView::item, QTreeView::item {{
    padding: 3px 6px;
    border-radius: 5px;
}}
QListView::item:selected, QTreeView::item:selected {{
    color: #ffffff;
    background: {accent};
}}
QListView::item:selected:!active, QTreeView::item:selected:!active,
QTableView::item:selected:!active {{
    color: {p["fg"]};
    background: {p["inactive"]};
}}
QTextEdit, QPlainTextEdit {{
    background: palette(base);
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 4px;
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent};
}}

Browser QTableView#tableView {{
    border: none;
    border-radius: 0;
    padding: 0;
    gridline-color: transparent;
    alternate-background-color: {p["alt"]};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
Browser QTableView#tableView QHeaderView::section {{
    color: {p["secondary"]};
    background: palette(base);
    border: none;
    border-bottom: 1px solid {p["sep"]};
    padding: 5px 8px;
    font-weight: 500;
}}
Browser QTableView#tableView QHeaderView::section:hover {{
    color: {p["fg"]};
}}

Browser SidebarTreeView {{
    background: {p["sidebar"]};
    border: none;
    border-radius: 0;
    padding: 4px 6px;
}}
Browser SidebarTreeView::item {{
    padding: 3px 2px;
    border-radius: 6px;
}}
Browser SidebarTreeView::item:hover:!selected {{
    background: {p["hover"]};
}}
Browser SidebarTreeView::item:selected {{
    color: #ffffff;
    background: {accent};
}}
Browser SidebarTreeView::item:selected:!active {{
    color: {p["fg"]};
    background: {p["inactive"]};
}}

CardLayout QTextEdit, CardLayout QPlainTextEdit {{
    font-family: "SF Mono", Menlo, monospace;
    font-size: 12px;
    padding: 6px 4px;
    background: palette(base);
    border: 1px solid {p["border"]};
    border-radius: 8px;
}}
CardLayout QTextEdit:focus, CardLayout QPlainTextEdit:focus {{
    border: 1px solid {accent};
}}
CardLayout QRadioButton {{
    padding: 4px 12px;
    border-radius: 6px;
    color: {p["fg"]};
}}
CardLayout QRadioButton::indicator {{
    width: 0;
    height: 0;
    image: none;
}}
CardLayout QRadioButton:hover:!checked {{
    background: {p["hover"]};
}}
CardLayout QRadioButton:checked {{
    background: palette(base);
    border: 1px solid {p["border"]};
}}

QFrame#mnReportFrame {{
    border: none;
}}

QFrame#mnPreviewDivider {{
    background: {p["sep"]};
    border: none;
}}

Browser QSplitter::handle {{
    background: {p["sep"]};
}}
Browser QSplitter::handle:horizontal {{
    width: 1px;
}}
Browser QSplitter::handle:vertical {{
    height: 1px;
}}
"""


def _round(menu: QMenu) -> None:
    """Give a menu (and its submenus) a transparent window so corners round.

    Must happen before the menu's native window exists, so it's done just
    before Anki opens a menu rather than after.
    """
    for m in [menu, *menu.findChildren(QMenu)]:
        if m.property(ROUNDED) is not True:
            m.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            m.setProperty(ROUNDED, True)
            m.style().unpolish(m)
            m.style().polish(m)


def _wrap(original: Callable) -> Callable:
    def opened(self, *args, **kwargs):
        try:
            _round(self)
        except Exception:
            pass
        return original(self, *args, **kwargs)

    return opened


def _browser_shown(browser) -> None:
    """No grid lines and a little more room per row, like an NSTableView."""
    view = browser.form.tableView
    view.setShowGrid(False)
    header = view.verticalHeader()
    header.setDefaultSectionSize(max(header.defaultSectionSize(), 26))


CHEVRON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path d='{d}' fill='none' stroke='{color}' stroke-width='1.8' "
    "stroke-linecap='round' stroke-linejoin='round'/></svg>"
)


def _chevron(direction: str):
    from aqt.qt import QIcon, QPixmap
    from aqt.theme import theme_manager

    color = "#ffffff" if theme_manager.night_mode else "#1d1d1f"
    d = "M10 3.5 5.5 8l4.5 4.5" if direction == "left" else "M6 3.5 10.5 8 6 12.5"
    pixmap = QPixmap()
    pixmap.loadFromData(CHEVRON.format(d=d, color=color).encode(), "SVG")
    return QIcon(pixmap)


def _patch_previewer() -> None:
    """Browser preview: chevron buttons instead of bare "<" and ">", a divider
    above the bar, and no default button (a preview has no primary action)."""
    from aqt.browser import previewer
    from aqt.qt import QDialogButtonBox, QFrame, QSize, QWidget

    original = previewer.MultiCardPreviewer._create_gui

    def create(self, *args, **kwargs):
        original(self, *args, **kwargs)
        window = self if isinstance(self, QWidget) else getattr(self, "_window", None)
        if window is not None:
            for bar in window.findChildren(QDialogButtonBox):
                for button in bar.findChildren(QPushButton):
                    button.setAutoDefault(False)
                    button.setDefault(False)
                bar.setContentsMargins(10, 8, 10, 10)
                layout = bar.parentWidget().layout() if bar.parentWidget() else None
                if layout is not None and layout.indexOf(bar) >= 0:
                    layout.setSpacing(0)  # divider sits right at the card's edge
                    divider = QFrame()
                    divider.setObjectName("mnPreviewDivider")
                    divider.setFixedHeight(1)
                    layout.insertWidget(layout.indexOf(bar), divider)
        for button, direction, tip in (
            (getattr(self, "_prev", None), "left", "Previous card"),
            (getattr(self, "_next", None), "right", "Next card"),
        ):
            if button is None:
                continue
            button.setText("")
            button.setIcon(_chevron(direction))
            button.setIconSize(QSize(14, 14))
            button.setToolTip(tip)
            button.setMinimumWidth(40)

    previewer.MultiCardPreviewer._create_gui = create


def _patch_find_duplicates() -> None:
    """Drop the square box around the duplicates report; the report draws
    its own grouped list."""
    from aqt.browser import find_duplicates

    original = find_duplicates.FindDuplicatesDialog.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        frame = self.form.webView.parentWidget()
        if frame is not None and frame is not self:
            frame.setObjectName("mnReportFrame")
            frame.style().unpolish(frame)
            frame.style().polish(frame)

    find_duplicates.FindDuplicatesDialog.__init__ = init


def _add_cards_opened(addcards) -> None:
    """Add is the window's main action, so draw it as the default button."""
    addcards.addButton.setDefault(True)


def _patch_preferences() -> None:
    """Preferences has no primary action; stop "Reset Window Sizes" from
    claiming the blue default-button look just because it comes first."""
    from aqt import preferences

    original = preferences.Preferences.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    preferences.Preferences.__init__ = init


def setup(accent: Callable[[], tuple[str, str]]) -> None:
    def current_qss() -> str:
        from aqt.theme import theme_manager

        light, dark = accent()
        night = theme_manager.night_mode
        return stylesheet(night, dark if night else light)

    def on_style(style: str) -> str:
        return style + current_qss()

    def ensure() -> None:
        # With the native macOS style in light mode, Anki sets no stylesheet
        # and style_did_init never runs, so add the rules directly. They
        # always sit at the end; replace them so a theme switch never leaves
        # the other appearance's colours behind.
        app = QApplication.instance()
        sheet = app.styleSheet()
        wanted = sheet.split(MARK)[0].rstrip() + current_qss()
        if wanted != sheet:
            app.setStyleSheet(wanted)

    gui_hooks.style_did_init.append(on_style)
    gui_hooks.theme_did_change.append(ensure)

    # Anki opens its menus from Python with exec()/popup(); round them there.
    for name in ("exec", "exec_", "popup"):
        if hasattr(QMenu, name):
            setattr(QMenu, name, _wrap(getattr(QMenu, name)))

    gui_hooks.browser_will_show.append(_browser_shown)
    gui_hooks.add_cards_did_init.append(_add_cards_opened)
    _patch_preferences()
    _patch_previewer()
    _patch_find_duplicates()

    def reapply() -> None:
        from aqt.theme import theme_manager

        theme_manager.apply_style()
        ensure()

    # The first style pass ran before add-ons loaded; run it again with ours.
    gui_hooks.profile_did_open.append(reapply)
