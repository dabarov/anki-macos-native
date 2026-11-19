"""Dev-only visual check. Loaded only when ANKI_MN_SNAPSHOT is set.

Walks deck list → overview → question → answer → deck list in light mode,
asking the Ask Claude panel two questions on the way, then repeats in dark
mode. Saves a PNG of the main window at each step. Switches Anki's theme
setting for the run and restores it at the end. Never answers a card, so
scheduling is untouched.
"""

from __future__ import annotations

import json
import os
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QTimer

OUT = os.environ["ANKI_MN_SNAPSHOT"]
os.makedirs(OUT, exist_ok=True)
_log = open(os.path.join(OUT, "log.txt"), "a", buffering=1)


def log(msg: str) -> None:
    _log.write(msg + "\n")


def snap(name: str) -> None:
    try:
        mw.grab().save(os.path.join(OUT, f"{name}.png"))
        log(f"saved {name}")
    except Exception:
        log(traceback.format_exc())


def set_theme(theme) -> None:
    """Switch Anki's theme setting; finish() puts the original back."""
    try:
        from aqt.theme import theme_manager

        mw.pm.set_theme(theme)
        theme_manager.apply_style()
        mw.reset()
        log(f"theme={theme} night_mode={theme_manager.night_mode}")
    except Exception:
        log("set_theme failed:\n" + traceback.format_exc())


def set_dark(on: bool) -> None:
    from aqt.theme import Theme

    set_theme(Theme.DARK if on else Theme.LIGHT)


WAIT_AI = object()  # step marker: wait until the panel's reply finishes


def _panel():
    from . import ai_panel

    return ai_panel._ensure()


def ai_send(text: str) -> None:
    p = _panel()
    p._js("mnAI && mnAI.focusComposer()")
    # Go through the UI path so the bubble/typing states render as for a user.
    p._js(
        "(function(){var t=document.querySelector('.ai-input');"
        f"t.value={json.dumps(text)};t.dispatchEvent(new Event('input'));"
        "document.querySelector('.ai-send').click();})()"
    )
    log(f"ai_send {text!r}")

    def report() -> None:
        keys = sorted({sc.key().toString() for sc in p._muted_shortcuts})
        log(f"muted while typing: {len(p._muted_shortcuts)} shortcuts {keys[:20]}, {len(p._muted_actions)} actions")

    QTimer.singleShot(300, report)


def tour(prefix: str, then=None, with_ai: bool = False) -> None:
    steps = [
        (0, lambda: mw.moveToState("deckBrowser")),
        (1800, lambda: snap(f"{prefix}1-decks")),
        (0, lambda: mw.moveToState("overview")),
        (1800, lambda: snap(f"{prefix}2-overview")),
        (0, lambda: mw.moveToState("review")),
        (2200, lambda: snap(f"{prefix}3-question")),
    ]
    if with_ai:
        steps += [
            (0, lambda: _panel().open()),
            (1500, lambda: snap(f"{prefix}3a-ai-empty")),
            (0, lambda: ai_send("Give me a hint")),
            (900, lambda: snap(f"{prefix}3b-ai-typing")),
            (0, WAIT_AI),
            (800, lambda: snap(f"{prefix}3c-ai-hint")),
        ]
    steps += [
        (0, lambda: mw.state == "review" and mw.reviewer._showAnswer()),
        (1500, lambda: snap(f"{prefix}4-answer")),
    ]
    if with_ai:
        steps += [
            (0, lambda: ai_send("Explain the answer")),
            (0, WAIT_AI),
            (800, lambda: snap(f"{prefix}4b-ai-explain")),
            (0, lambda: log("messages: " + repr(_panel().messages))),
        ]
    else:
        steps += [
            (0, lambda: _panel().open()),
            (1500, lambda: snap(f"{prefix}4b-ai-explain")),
        ]
    steps += [
        (0, lambda: _panel().close()),
        (0, lambda: mw.moveToState("deckBrowser")),
        (1800, lambda: snap(f"{prefix}5-decks-again")),
    ]

    def run(i: int) -> None:
        if i >= len(steps):
            if then:
                then()
            return
        delay, fn = steps[i]

        if fn is WAIT_AI:
            started = [0]

            def poll() -> None:
                started[0] += 1
                busy = _panel().run is not None
                if busy and started[0] < 120:  # up to 60s
                    QTimer.singleShot(500, poll)
                else:
                    log(f"ai wait done busy={busy} after {started[0] * 0.5:.1f}s")
                    run(i + 1)

            QTimer.singleShot(1000, poll)
            return

        def go() -> None:
            try:
                fn()
            except Exception:
                log(traceback.format_exc())
            run(i + 1)

        QTimer.singleShot(delay, go)

    run(0)


_original_theme = None


def start() -> None:
    global _original_theme
    _original_theme = mw.pm.theme()
    log(f"state={mw.state} original_theme={_original_theme}; starting tour")
    set_dark(False)
    QTimer.singleShot(
        1500,
        lambda: tour(
            "light-",
            with_ai=True,
            then=lambda: (
                set_dark(True),
                QTimer.singleShot(1500, lambda: tour("dark-", then=finish)),
            ),
        ),
    )


def finish() -> None:
    if _original_theme is not None:
        set_theme(_original_theme)
    log("done")


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(2500, start))
