"""Dev-only typography audit. Loaded when ANKI_MN_AUDIT is set to a folder.

Visits each screen, reads the computed font of key elements in every
webview, and checks which face actually renders (by comparing text widths
against reference fonts). Writes fonts.json and screenshots to the folder.
"""

from __future__ import annotations

import json
import os
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QTimer

OUT = os.environ["ANKI_MN_AUDIT"]
os.makedirs(OUT, exist_ok=True)
RESULTS: dict = {}
_log = open(os.path.join(OUT, "audit-log.txt"), "a", buffering=1)


def log(msg: str) -> None:
    _log.write(msg + "\n")


PROBE_JS = r"""
(function(selectors){
  var c = document.createElement('canvas').getContext('2d');
  var sample = 'Hamburgefonstiv 0123456789';
  function width(font){ c.font = font; return c.measureText(sample).width; }
  function face(cs){
    var base = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ';
    var used = width(base + cs.fontFamily);
    var refs = {
      'SF (system-ui)': width(base + 'system-ui'),
      'Arial': width(base + 'Arial'),
      'Helvetica': width(base + 'Helvetica'),
      'Times': width(base + 'Times'),
      'SF Mono': width(base + 'ui-monospace'),
    };
    var best = null, diff = 1e9;
    for (var k in refs) { var d = Math.abs(refs[k] - used); if (d < diff) { diff = d; best = k; } }
    return diff < 0.5 ? best : ('other (' + cs.fontFamily.slice(0, 40) + ')');
  }
  var out = [];
  selectors.forEach(function(sel){
    var el = document.querySelector(sel);
    if (!el) { out.push({sel: sel, missing: true}); return; }
    var cs = getComputedStyle(el);
    out.push({
      sel: sel,
      text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 30),
      face: face(cs),
      family: cs.fontFamily.slice(0, 60),
      size: cs.fontSize, weight: cs.fontWeight, lineHeight: cs.lineHeight,
      tracking: cs.letterSpacing, smoothing: cs.webkitFontSmoothing || '',
      color: cs.color
    });
  });
  return out;
})(%s)
"""

SELECTORS = {
    "toolbar": [".toolbar .hitem", "#mn-ai"],
    "decks": ["center > table th", "a.deck", "tr.deck td[align=end] span", "#studiedToday"],
    "overview": ["h3", "center table table td:first-child", "center table table td:last-child b", "#study"],
    "bottombar": ["button"],
    "question": ["body", ".card", "#qa"],
    "answer": [".card", "#qa"],
    "reviewer-bar": ["#ansbut", "td.stat button", ".stattxt", "button[data-ease]", ".nobold"],
    "panel": [".ai-title", ".ai-chip", ".ai-deck", ".ai-empty h2", ".ai-empty p", ".ai-chipbtn",
              ".ai-input", ".ai-note", ".ai-text p", ".ai-text strong", ".ai-text li", ".ai-text code"],
}


def probe(name: str, web, then) -> None:
    js = PROBE_JS % json.dumps(SELECTORS[name])

    def cb(result) -> None:
        RESULTS[name] = result
        log(f"probed {name}")
        then()

    try:
        web.evalWithCallback(js, cb)
    except Exception:
        log(traceback.format_exc())
        then()


def snap(name: str) -> None:
    mw.grab().save(os.path.join(OUT, f"{name}.png"))


def chain(steps) -> None:
    def run(i: int) -> None:
        if i >= len(steps):
            return
        delay, fn = steps[i]

        def go() -> None:
            try:
                if fn.__code__.co_argcount == 1:
                    fn(lambda: run(i + 1))
                    return
                fn()
            except Exception:
                log(traceback.format_exc())
            run(i + 1)

        QTimer.singleShot(delay, go)

    run(0)


def _panel():
    from . import ai_panel

    return ai_panel._ensure()


def finish() -> None:
    notetypes = []
    try:
        for m in mw.col.models.all():
            notetypes.append({"name": m["name"], "css": m.get("css", "")})
    except Exception:
        log(traceback.format_exc())
    RESULTS["notetypes"] = notetypes
    with open(os.path.join(OUT, "fonts.json"), "w") as f:
        json.dump(RESULTS, f, indent=1)
    log("done")


def start() -> None:
    sample_reply = (
        "The answer is **Hello**. It pairs one greeting with another.\\n\\n"
        "- As a reply: someone says `Hi`, you say Hello.\\n- As a synonym."
    )
    chain([
        (0, lambda: mw.moveToState("deckBrowser")),
        (1500, lambda nxt: probe("decks", mw.web, nxt)),
        (0, lambda nxt: probe("bottombar", mw.bottomWeb, nxt)),
        (0, lambda nxt: probe("toolbar", mw.toolbar.web, nxt)),
        (0, lambda: mw.moveToState("overview")),
        (1500, lambda nxt: probe("overview", mw.web, nxt)),
        (0, lambda: mw.moveToState("review")),
        (2000, lambda nxt: probe("question", mw.web, nxt)),
        (0, lambda nxt: probe("reviewer-bar", mw.bottomWeb, nxt)),
        (0, lambda: _panel().open()),
        (1500, lambda: _panel()._js(f"mnAI.delta(\"{sample_reply}\");mnAI.done()")),
        (600, lambda nxt: probe("panel", _panel().web, nxt)),
        (0, lambda: snap("question-with-panel")),
        (0, lambda: mw.reviewer._showAnswer()),
        (1200, lambda nxt: probe("answer", mw.web, nxt)),
        (0, lambda nxt: probe("reviewer-bar", mw.bottomWeb, nxt)),
        (0, lambda: snap("answer-with-panel")),
        (0, lambda: _panel().close()),
        (0, lambda: mw.moveToState("deckBrowser")),
        (500, finish),
    ])


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(2500, start))
