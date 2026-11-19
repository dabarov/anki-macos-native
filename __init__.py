"""macOS Native — restyles Anki's main window to feel at home on macOS 26.

Anki draws its main window (top toolbar, deck list, deck overview, review
screen and bottom bar) as web pages. This add-on appends one stylesheet and
one small script to each of those pages; it never edits Anki's own files and
never touches your card templates. Disable it in Tools → Add-ons to go back.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from aqt import gui_hooks, mw

ADDON = mw.addonManager.addonFromModule(__name__)
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js|svg)")

# Which Anki page each webview context renders. Matched by class name so the
# add-on doesn't break if Anki moves these classes between modules.
SCREENS = {
    "Toolbar": "toolbar",
    "TopToolbar": "toolbar",
    "DeckBrowser": "decks",
    "DeckBrowserBottomBar": "bottombar",
    "Overview": "overview",
    "OverviewBottomBar": "bottombar",
    "Reviewer": "reviewer",
    "ReviewerBottomBar": "reviewer-bar",
    "AIPanel": "ai",
}

# macOS accent colours (NSColor.controlAccentColor), light / dark.
# Keys are the values of `defaults read -g AppleAccentColor`; missing = blue.
ACCENTS = {
    "-1": ("#8c8c8c", "#989898"),  # graphite
    "0": ("#ff3b30", "#ff453a"),  # red
    "1": ("#ff9500", "#ff9f0a"),  # orange
    "2": ("#ffcc00", "#ffd60a"),  # yellow
    "3": ("#28cd41", "#32d74b"),  # green
    "4": ("#007aff", "#0a84ff"),  # blue
    "5": ("#af52de", "#bf5af2"),  # purple
    "6": ("#ff2d55", "#ff375f"),  # pink
}


def _config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


def _system_accent() -> tuple[str, str]:
    """Read the accent colour picked in System Settings → Appearance."""
    if sys.platform != "darwin":
        return ACCENTS["4"]
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleAccentColor"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        key = out.stdout.strip() if out.returncode == 0 else "4"
    except Exception:
        key = "4"
    return ACCENTS.get(key, ACCENTS["4"])


_ACCENT = _system_accent()


def _accent() -> tuple[str, str]:
    custom = str(_config().get("accent", "system")).strip()
    if custom.startswith("#") and len(custom) in (4, 7):
        return (custom, custom)
    return _ACCENT


def on_webview_will_set_content(web_content, context) -> None:
    screen = SCREENS.get(type(context).__name__)
    if not screen:
        return
    light, dark = _accent()
    cfg = _config()
    base = f"/_addons/{ADDON}/web"
    web_content.css.append(f"{base}/macos.css")
    web_content.js.append(f"{base}/macos.js")
    if screen == "ai":
        web_content.css.append(f"{base}/ai-panel.css")
        web_content.js.append(f"{base}/ai-panel.js")
    # Set before <body> is parsed so the first paint is already themed.
    web_content.head += (
        "<script>"
        f"document.documentElement.dataset.mn={json.dumps(screen)};"
        f"document.documentElement.dataset.mnMotion={json.dumps('on' if cfg.get('motion', True) else 'off')};"
        "</script>"
        f"<style>:root{{--mn-accent-light:{light};--mn-accent-dark:{dark};}}</style>"
    )


gui_hooks.webview_will_set_content.append(on_webview_will_set_content)

# Cards: Anki's stock note types ship `font-family: arial`, which clashes with
# the SF interface around them. When a card still uses that stock font, show it
# in the system font on the review screen. Display only: note types aren't
# edited, a font you picked yourself is left alone, and the card template
# editor still shows exactly what your CSS says.
_STOCK_ARIAL = re.compile(r"font-family\s*:\s*['\"]?arial['\"]?\s*;", re.I)
_SYSTEM_CARD_FONT = (
    "<style>html .card{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;}</style>"
)


def on_card_will_show(text: str, card, kind: str) -> str:
    if not kind.startswith("review") or _config().get("card_font", "system") != "system":
        return text
    try:
        css = card.note_type()["css"]
    except Exception:
        return text
    return text + _SYSTEM_CARD_FONT if _STOCK_ARIAL.search(css) else text


gui_hooks.card_will_show.append(on_card_will_show)

# "Ask AI" side panel. Kept isolated: if it fails, the theme still loads.
try:
    from . import ai_panel

    ai_panel.setup()
except Exception:
    import traceback

    print("macOS Native: Ask AI panel disabled\n" + traceback.format_exc())

# Dev-only tools, inert unless their variable names an output folder:
# ANKI_MN_SNAPSHOT saves each screen as PNG (no screen-recording permission
# needed); ANKI_MN_AUDIT writes the computed fonts of every screen.
if os.environ.get("ANKI_MN_SNAPSHOT"):
    from . import snapshot  # noqa: F401
if os.environ.get("ANKI_MN_AUDIT"):
    from . import audit  # noqa: F401
