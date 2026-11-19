"""Ask AI: a side panel for questions about the card you're reviewing.

Pick Claude, ChatGPT, Gemini or a local Ollama model from the panel's title.
One conversation per card, which every provider shares, so you can switch
mid-thread to compare answers. While the answer is still hidden, the model
only sees the question and is told to give hints rather than the answer.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Optional

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QDockWidget,
    QKeySequence,
    QShortcut,
    Qt,
    QTimer,
    QWidget,
)
from aqt.webview import AnkiWebView

from . import providers

ADDON_DIR = os.path.dirname(__file__)
WORKDIR = os.path.join(ADDON_DIR, "user_files", "ai-workdir")
TOGGLE_KEY = "Ctrl+Alt+I"  # ⌥⌘I on macOS, the usual "show inspector" key
TOGGLE_LABEL = "⌥⌘I"

SYSTEM_PROMPT = """\
You are {name}, helping a student who is reviewing flashcards in Anki. You \
sit in a narrow side panel next to the card they are looking at.

The student's message comes with the card's text. When the answer is \
marked hidden, the student has not revealed it yet: do not state it. Give \
a hint that moves them toward it, and reveal it only if they ask you to.

Write for a narrow panel: keep replies under about 80 words unless the \
student asks for more, in short paragraphs or a short list. Explain the idea \
behind the card rather than restating it, and add one concrete example when \
it helps. If the card looks wrong or ambiguous, say so plainly. Reply in the \
language the student writes in. Answer from what you know; don't run tools \
or read files."""

SIGN_IN = {
    "claude": "Run <code>claude</code> in Terminal and sign in, then try again.",
    "codex": "Open ChatGPT and sign in, or run <code>codex login</code> in Terminal.",
    "gemini": "Run <code>gemini</code> in Terminal and sign in, then try again.",
}


# ── Card text ───────────────────────────────────────────────────────

def _html_to_text(raw: str) -> str:
    s = re.sub(r"(?is)<(style|script)\b[^>]*>.*?</\1>", "", raw)
    s = re.sub(r"\[sound:[^\]]+\]", "[audio]", s)
    s = re.sub(r"(?i)<img\b[^>]*>", "[image]", s)
    s = re.sub(r"(?i)<br\s*/?>|</(div|p|li|tr|h[1-6]|blockquote)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def _answer_only(answer_html: str) -> str:
    # Standard templates render {{FrontSide}}<hr id=answer>Back.
    parts = re.split(r"(?i)<hr[^>]*id=['\"]?answer['\"]?[^>]*>", answer_html, maxsplit=1)
    return parts[1] if len(parts) == 2 else answer_html


def current_card_context() -> dict:
    if mw.state != "review" or not getattr(mw.reviewer, "card", None):
        return {"state": "none"}
    card = mw.reviewer.card
    revealed = getattr(mw.reviewer, "state", "") == "answer"
    try:
        deck = mw.col.decks.name(card.current_deck_id())
    except Exception:
        deck = ""
    ctx = {
        "state": "card",
        "cardId": card.id,
        "deck": deck,
        "revealed": revealed,
        "question": _html_to_text(card.question()),
    }
    if revealed:
        ctx["answer"] = _html_to_text(_answer_only(card.answer()))
    return ctx


def card_block(ctx: dict) -> str:
    if ctx.get("state") != "card":
        return "(No card is open right now.)"
    lines = [
        f'<card deck="{html.escape(ctx.get("deck", ""))}">',
        f"<question>\n{ctx['question']}\n</question>",
    ]
    if ctx.get("revealed"):
        lines.append(f"<answer>\n{ctx.get('answer', '')}\n</answer>")
    else:
        lines.append(
            "<answer>(The card has an answer, but the student hasn't revealed it yet, "
            "so it isn't shown to you either.)</answer>"
        )
    lines.append("</card>")
    return "\n".join(lines)


def build_prompt(ctx: dict, history: list[dict], latest: str) -> str:
    """One self-contained prompt, for the CLI providers."""
    out = [card_block(ctx)]
    if history:
        out.append("\n<conversation_so_far>")
        for m in history:
            who = "Student" if m["role"] == "user" else "Tutor"
            out.append(f"{who}: {m['text']}")
        out.append("</conversation_so_far>")
    out.append(f"\nStudent: {latest}")
    return "\n".join(out)


def build_chat(ctx: dict, history: list[dict], latest: str) -> list[dict]:
    """Chat messages, for providers with a native chat API (Ollama)."""
    msgs = [{"role": m["role"], "content": m["text"]} for m in history]
    msgs.append({"role": "user", "content": f"{card_block(ctx)}\n\n{latest}"})
    return msgs


# ── Panel ───────────────────────────────────────────────────────────

class AIPanel:
    """Named AIPanel: the theme hook maps this class name to its styles."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.card_id: Optional[int] = None
        self.run = None
        self.partial = ""
        self.loaded = False
        self.catalog: list[dict] = []
        self.provider_id = "claude"
        self._run_provider: dict = {}
        self._muted_shortcuts: list[QShortcut] = []
        self._muted_actions: list[tuple[QAction, list]] = []

        self.dock = QDockWidget(mw)
        self.dock.setObjectName("mnAskAI")
        self.dock.setWindowTitle("Ask AI")
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.dock.setTitleBarWidget(QWidget())  # header is drawn in the web view
        self.dock.setMinimumWidth(300)

        try:
            from aqt.webview import AnkiWebViewKind

            self.web = AnkiWebView(parent=self.dock, title="Ask AI", kind=AnkiWebViewKind.DEFAULT)
        except Exception:
            self.web = AnkiWebView(parent=self.dock, title="Ask AI")
        self.web.set_bridge_command(self._on_bridge, self)
        self.dock.setWidget(self.web)

        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.hide()
        self.dock.visibilityChanged.connect(self._on_visibility)
        self._style_separator()

        # Safety net: whenever keyboard focus leaves the panel, review keys
        # come back, even if the page never reported a blur.
        from aqt.qt import QApplication

        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    # providers -------------------------------------------------------

    def _cfg(self) -> dict:
        return mw.addonManager.getConfig(__name__) or {}

    def refresh_providers(self) -> None:
        self.catalog = providers.catalog(self._cfg())
        if mw.pm.profile is not None:
            self.provider_id = mw.pm.profile.get("mn_ai_provider", self.provider_id)

    def provider(self) -> Optional[dict]:
        chat = [p for p in self.catalog if p["kind"] != "action"]
        for p in chat:
            if p["id"] == self.provider_id:
                return p
        return next((p for p in chat if p["available"]), chat[0] if chat else None)

    def select(self, provider_id: str) -> None:
        if provider_id == "ollama:start":
            providers.start_ollama()
            self._js("mnAI && mnAI.setStarting(true)")
            QTimer.singleShot(3000, self._after_ollama_start)
            return
        self.provider_id = provider_id
        if mw.pm.profile is not None:
            mw.pm.profile["mn_ai_provider"] = provider_id
        self._push_context()

    def _after_ollama_start(self) -> None:
        self.refresh_providers()
        ollama = [p for p in self.catalog if p["kind"] == "ollama"]
        if ollama and not self.provider()["id"].startswith("ollama:"):
            self.select(ollama[0]["id"])
        else:
            self._push_context()
        self._js("mnAI && mnAI.setStarting(false)")

    # visibility ------------------------------------------------------

    def is_open(self) -> bool:
        return self.dock.isVisible()

    def toggle(self) -> None:
        self.close() if self.is_open() else self.open()

    def open(self) -> None:
        if not self.loaded:
            self.web.stdHtml('<div id="mn-ai"></div>', context=self)
            self.loaded = True
        self.refresh_providers()
        self.dock.show()
        width = int(mw.pm.profile.get("mn_ai_width", 360)) if mw.pm.profile else 360
        mw.resizeDocks([self.dock], [width], Qt.Orientation.Horizontal)
        self.sync_card()
        self.web.setFocus()
        self._js("mnAI && mnAI.focusComposer()")

    def close(self) -> None:
        self.dock.hide()
        mw.web.setFocus()

    def _on_visibility(self, visible: bool) -> None:
        if not visible:
            self._mute_shortcuts(False)
            if mw.pm.profile is not None and self.dock.width() > 0:
                mw.pm.profile["mn_ai_width"] = self.dock.width()
        if mw.pm.profile is not None:
            mw.pm.profile["mn_ai_open"] = visible
        try:
            mw.toolbar.web.eval(
                "(function(){var e=document.getElementById('mn-ai');"
                f"if(e)e.classList.toggle('mn-active',{json.dumps(visible)});}})()"
            )
        except Exception:
            pass

    def _style_separator(self) -> None:
        from aqt.theme import theme_manager

        color = "#1c1c1c" if theme_manager.night_mode else "#d9d9d9"
        mw.setStyleSheet(f"QMainWindow::separator {{ width: 1px; background: {color}; }}")

    # card tracking ---------------------------------------------------

    def sync_card(self) -> None:
        ctx = current_card_context()
        card_id = ctx.get("cardId")
        # Reset only when a different card comes up. Stepping out to the
        # deck list and back to the same card keeps the conversation.
        if card_id is not None and card_id != self.card_id:
            self.card_id = card_id
            self._cancel_run()
            self.messages = []
            self._js("mnAI && mnAI.reset()")
        self._push_context(ctx)

    def _push_context(self, ctx: Optional[dict] = None) -> None:
        ctx = ctx or current_card_context()
        current = self.provider()
        view = {
            "state": ctx.get("state"),
            "deck": ctx.get("deck", ""),
            "revealed": bool(ctx.get("revealed")),
            "shortcut": TOGGLE_LABEL,
            "provider": current["id"] if current else None,
            "providers": [
                {k: p.get(k) for k in ("id", "kind", "group", "name", "detail", "available", "reason")}
                for p in self.catalog
            ],
        }
        self._js(f"mnAI && mnAI.setContext({json.dumps(view)})")

    # bridge ----------------------------------------------------------

    def _on_bridge(self, cmd: str):
        if not cmd.startswith("mnai:"):
            return None
        try:
            msg = json.loads(cmd[5:])
        except ValueError:
            return None
        kind = msg.get("type")
        if kind == "ready":
            self._push_context()
        elif kind == "send":
            self.send(str(msg.get("text", "")).strip())
        elif kind == "stop":
            self.stop()
        elif kind == "new":
            self._cancel_run()
            self.messages = []
            self._js("mnAI && mnAI.reset()")
            self._push_context()
        elif kind == "select":
            self.select(str(msg.get("id", "")))
        elif kind == "refresh":
            self.refresh_providers()
            self._push_context()
        elif kind == "close":
            self.close()
        elif kind == "focus":
            self._mute_shortcuts(True)
        elif kind == "blur":
            self._mute_shortcuts(False)
        return None

    # conversation ----------------------------------------------------

    def send(self, text: str) -> None:
        if not text or self.run:
            return
        provider = self.provider()
        if not provider or not provider.get("available"):
            reason = (provider or {}).get("reason") or "Pick a model from the menu at the top of the panel."
            self._js(f"mnAI && mnAI.error({json.dumps(reason)}, 'missing')")
            return
        cfg = self._cfg()
        ctx = current_card_context()
        name = provider["name"]
        system = SYSTEM_PROMPT.format(name=name if provider["kind"] != "ollama" else "a study assistant")
        history = list(self.messages)
        self.messages.append({"role": "user", "text": text})
        self.partial = ""

        def on_delta(chunk: str) -> None:
            mw.taskman.run_on_main(lambda: self._delta(run_ref[0], chunk))

        def on_done() -> None:
            mw.taskman.run_on_main(lambda: self._finish(run_ref[0], None))

        def on_error(message: str) -> None:
            mw.taskman.run_on_main(lambda: self._finish(run_ref[0], message))

        run_ref: list = [None]
        self._run_provider = provider
        try:
            run_ref[0] = providers.start_run(
                provider,
                cfg,
                system,
                build_prompt(ctx, history, text),
                build_chat(ctx, history, text),
                WORKDIR,
                on_delta,
                on_done,
                on_error,
            )
        except Exception as exc:
            self.messages.pop()
            self._js(f"mnAI && mnAI.error({json.dumps(str(exc))}, 'error')")
            return
        self.run = run_ref[0]

    def _delta(self, run, chunk: str) -> None:
        if run is None or run is not self.run:
            return
        self.partial += chunk
        self._js(f"mnAI && mnAI.delta({json.dumps(chunk)})")

    def _record_partial(self) -> None:
        if self.partial:
            self.messages.append({
                "role": "assistant",
                "text": self.partial,
                "provider": self._run_provider.get("name", ""),
            })
        elif self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()  # nothing came back; let them retry cleanly
        self.partial = ""

    def _finish(self, run, error: Optional[str]) -> None:
        if run is None or run is not self.run:
            return
        self.run = None
        self._record_partial()
        if error:
            kind = self._run_provider.get("kind", "")
            signin = kind in SIGN_IN and re.search(r"log ?in|sign ?in|/login|auth|credential|401", error, re.I)
            hint = SIGN_IN[kind] if signin else ""
            self._js(f"mnAI && mnAI.error({json.dumps(error)}, {json.dumps('signin' if signin else 'error')}, {json.dumps(hint)})")
        else:
            self._js("mnAI && mnAI.done()")

    def stop(self) -> None:
        run = self.run
        if not run:
            return
        run.cancel()
        self.run = None
        self._record_partial()
        self._js("mnAI && mnAI.done(true)")

    def _cancel_run(self) -> None:
        if self.run:
            self.run.cancel()
            self.run = None
        self.partial = ""

    # typing safety -----------------------------------------------------
    # Anki's review keys (Space, 1–4, e, r, …) are window-wide shortcuts, so
    # they'd fire while typing in the panel. Mute every unmodified one while
    # the composer has focus; ⌘-shortcuts keep working.

    @staticmethod
    def _is_plain(seq: QKeySequence) -> bool:
        if seq.isEmpty():
            return False
        mods = seq[0].keyboardModifiers()
        blocking = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        return not (mods & blocking)

    def _mute_shortcuts(self, mute: bool) -> None:
        if mute:
            for sc in mw.findChildren(QShortcut):
                if sc.isEnabled() and self._is_plain(sc.key()) and sc not in self._muted_shortcuts:
                    sc.setEnabled(False)
                    self._muted_shortcuts.append(sc)
            for act in mw.findChildren(QAction):
                keys = act.shortcuts()
                if keys and any(self._is_plain(k) for k in keys):
                    if all(a is not act for a, _ in self._muted_actions):
                        self._muted_actions.append((act, keys))
                        act.setShortcuts([k for k in keys if not self._is_plain(k)])
        else:
            for sc in self._muted_shortcuts:
                try:
                    sc.setEnabled(True)
                except RuntimeError:  # deleted when Anki changed screens
                    pass
            for act, keys in self._muted_actions:
                try:
                    act.setShortcuts(keys)
                except RuntimeError:
                    pass
            self._muted_shortcuts = []
            self._muted_actions = []

    def _on_focus_changed(self, _old, new) -> None:
        if not (self._muted_shortcuts or self._muted_actions):
            return
        widget = new
        while widget is not None:
            if widget is self.dock:
                return
            widget = widget.parentWidget()
        self._mute_shortcuts(False)

    def _state_changed(self) -> None:
        # Changing screens rebuilds Anki's shortcuts; re-mute if still typing.
        if self._muted_shortcuts or self._muted_actions:
            self._mute_shortcuts(True)

    # misc -------------------------------------------------------------

    def _js(self, code: str) -> None:
        if self.loaded:
            self.web.eval(code)

    def shutdown(self) -> None:
        self._cancel_run()
        self._mute_shortcuts(False)


panel: Optional[AIPanel] = None


def _ensure() -> AIPanel:
    global panel
    if panel is None:
        panel = AIPanel()
    return panel


def setup() -> None:
    def add_link(links: list, toolbar) -> None:
        links.append(
            toolbar.create_link(
                "mn-ai",
                "Ask AI",
                lambda: _ensure().toggle(),
                tip=f"Ask an AI about this card ({TOGGLE_LABEL})",
                id="mn-ai",
            )
        )

    gui_hooks.top_toolbar_did_init_links.append(add_link)

    action = QAction("Ask AI", mw)
    action.setShortcut(QKeySequence(TOGGLE_KEY))
    action.triggered.connect(lambda: _ensure().toggle())
    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addAction(action)

    def on_card(*_args) -> None:
        if panel and panel.loaded:
            panel.sync_card()

    def on_state(*_args) -> None:
        if panel:
            panel._state_changed()
            if panel.loaded:
                panel.sync_card()

    def on_theme(*_args) -> None:
        if panel:
            panel._style_separator()

    def on_profile_open() -> None:
        try:
            mw.toolbar.draw()
        except Exception:
            pass
        if mw.pm.profile and mw.pm.profile.get("mn_ai_open"):
            _ensure().open()

    def on_profile_close() -> None:
        if panel:
            panel.shutdown()

    gui_hooks.reviewer_did_show_question.append(on_card)
    gui_hooks.reviewer_did_show_answer.append(on_card)
    gui_hooks.state_did_change.append(on_state)
    gui_hooks.theme_did_change.append(on_theme)
    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.profile_will_close.append(on_profile_close)
