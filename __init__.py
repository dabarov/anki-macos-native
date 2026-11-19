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
import urllib.parse

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
    "BrowserPreviewer": "reviewer",
    "Previewer": "reviewer",
    "MultiCardPreviewer": "reviewer",
    "ReviewerBottomBar": "reviewer-bar",
    "AIPanel": "ai",
    "Editor": "editor",
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


# Web views that render cards keep exactly what the note type's CSS says.
CARD_RENDERERS = {"CardLayout"}


def screen_for(context) -> str | None:
    """Known screens get their own styles. Anything else, such as About, Find
    Duplicates, Empty Cards, or a screen a newer Anki adds, gets the generic
    page theme, so new windows match without a change here."""
    name = type(context).__name__
    if name in SCREENS:
        return SCREENS[name]
    if name in CARD_RENDERERS:
        return None
    return "page"


def on_webview_will_set_content(web_content, context) -> None:
    screen = screen_for(context)
    if not screen:
        return
    light, dark = _accent()
    cfg = _config()
    base = f"/_addons/{ADDON}/web"
    web_content.css.append(f"{base}/macos.css")
    web_content.js.append(f"{base}/macos.js")
    if screen == "page":
        web_content.css.append(f"{base}/pages.css")
    elif screen == "ai":
        web_content.css.append(f"{base}/ai-panel.css")
        web_content.js.append(f"{base}/ai-panel.js")
    elif screen == "editor":
        web_content.css.append(f"{base}/editor.css")
        query = urllib.parse.urlencode({"light": light, "dark": dark, "font": cfg.get("card_font", "system")})
        web_content.js.append(f"{base}/editor.js?{query}")
    # Set before <body> is parsed so the first paint is already themed.
    web_content.head += (
        "<script>"
        f"document.documentElement.dataset.mn={json.dumps(screen)};"
        f"document.documentElement.dataset.mnMotion={json.dumps('on' if cfg.get('motion', True) else 'off')};"
        f"document.documentElement.dataset.mnCardFont={json.dumps(cfg.get('card_font', 'system'))};"
        "</script>"
        f"<style>:root{{--mn-accent-light:{light};--mn-accent-dark:{dark};}}</style>"
    )


gui_hooks.webview_will_set_content.append(on_webview_will_set_content)

# Cards: Anki's stock note types ship `font-family: arial`, which clashes with
# the SF interface around them. When a card still uses that stock font, show it
# in the system font on the review screen and in previews. Display only: note types aren't
# edited, a font you picked yourself is left alone, and the card template
# editor still shows exactly what your CSS says.
_STOCK_ARIAL = re.compile(r"font-family\s*:\s*['\"]?arial['\"]?\s*;", re.I)
_SYSTEM_CARD_FONT = (
    "<style>html .card{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;}</style>"
)


def on_card_will_show(text: str, card, kind: str) -> str:
    # Review screen and Browser preview; never the card template editor.
    if not kind.startswith(("review", "preview")) or _config().get("card_font", "system") != "system":
        return text
    try:
        css = card.note_type()["css"]
    except Exception:
        return text
    return text + _SYSTEM_CARD_FONT if _STOCK_ARIAL.search(css) else text


gui_hooks.card_will_show.append(on_card_will_show)


# Svelte pages (deck Options, Card Info, Change Notetype, …) don't go through
# webview_will_set_content, so their styles are added once Anki has injected
# its own.
def on_page_styled(webview) -> None:
    light, dark = _accent()
    base = f"/_addons/{ADDON}/web"
    webview.eval(
        "(function(){var d=document.documentElement;"
        "if(d.dataset.mn)return;"
        "d.dataset.mn='page';"
        f"d.style.setProperty('--mn-accent-light',{json.dumps(light)});"
        f"d.style.setProperty('--mn-accent-dark',{json.dumps(dark)});"
        f"[{json.dumps(base + '/macos.css')},{json.dumps(base + '/pages.css')}].forEach(function(h){{"
        "var l=document.createElement('link');l.rel='stylesheet';l.href=h;document.head.appendChild(l);});"
        "})()"
    )


gui_hooks.webview_did_inject_style_into_page.append(on_page_styled)

# Pop-up menus (deck ⋯, review More, context menus).
try:
    from . import qt_style

    qt_style.setup(_accent)
except Exception:
    import traceback

    print("macOS Native: menu styling disabled\n" + traceback.format_exc())

# "Ask AI" side panel. Kept isolated: if it fails, the theme still loads.
try:
    from . import ai_panel

    ai_panel.setup()
except Exception:
    import traceback

    print("macOS Native: Ask AI panel disabled\n" + traceback.format_exc())

# Dev-only tools, inert unless their variable names an output folder:
# ANKI_MN_SNAPSHOT saves each screen as PNG (no screen-recording permission
# needed); ANKI_MN_AUDIT writes the computed fonts of every screen;
# ANKI_MN_SWEEP opens and captures every window in light and dark.
if os.environ.get("ANKI_MN_SNAPSHOT"):
    from . import snapshot  # noqa: F401
if os.environ.get("ANKI_MN_AUDIT"):
    from . import audit  # noqa: F401
if os.environ.get("ANKI_MN_SWEEP"):
    from . import sweep  # noqa: F401
