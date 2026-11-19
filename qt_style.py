"""Native-feeling Qt pop-up menus: the deck ⋯ menu, the review More menu and
every other context menu Anki opens.

Anki draws these with its own flat Qt stylesheet. This adds macOS 26 menu
styling on top: rounded corners, an inset accent highlight, inset separators
and system colours for light and dark.
"""

from __future__ import annotations

from typing import Callable

from aqt import gui_hooks
from aqt.qt import QApplication, QMenu, Qt

ROUNDED = "mnRounded"
MARK = "/* macos-native menus */"


def _palette(dark: bool) -> dict:
    if dark:
        return {
            "bg": "#2b2b2d", "border": "rgba(255, 255, 255, 0.14)", "fg": "rgba(255, 255, 255, 0.88)",
            "disabled": "rgba(255, 255, 255, 0.3)", "sep": "rgba(255, 255, 255, 0.12)",
        }
    return {
        "bg": "#f6f6f6", "border": "rgba(0, 0, 0, 0.14)", "fg": "rgba(0, 0, 0, 0.86)",
        "disabled": "rgba(0, 0, 0, 0.28)", "sep": "rgba(0, 0, 0, 0.1)",
    }


def menu_stylesheet(dark: bool, accent: str) -> str:
    p = _palette(dark)
    return f"""
{MARK}
QMenu {{
    background-color: {p["bg"]};
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


def setup(accent: Callable[[], tuple[str, str]]) -> None:
    def current_qss() -> str:
        from aqt.theme import theme_manager

        light, dark = accent()
        night = theme_manager.night_mode
        return menu_stylesheet(night, dark if night else light)

    def on_style(style: str) -> str:
        return style + current_qss()

    def ensure() -> None:
        # With the native macOS style in light mode, Anki sets no stylesheet
        # and style_did_init never runs, so add the menu rules directly.
        # Our rules always sit at the end; replace them so a theme switch
        # never leaves the other appearance's colours behind.
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

    def reapply() -> None:
        from aqt.theme import theme_manager

        theme_manager.apply_style()
        ensure()

    # The first style pass ran before add-ons loaded; run it again with ours.
    gui_hooks.profile_did_open.append(reapply)
