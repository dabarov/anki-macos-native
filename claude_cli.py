"""Runs one Claude turn through the locally installed Claude Code CLI.

Uses the user's existing Claude Code sign-in, so no API key lives in Anki.
Claude Code is started with every tool, MCP server, skill and settings file
switched off: inside Anki it can only read the text we hand it and reply.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from typing import Callable, Optional

HOME = os.path.expanduser("~")

# Anki launched from the Dock gets a minimal PATH, so look in the usual
# install locations as well as PATH.
CANDIDATES = [
    os.path.join(HOME, ".local", "bin", "claude"),
    os.path.join(HOME, ".claude", "local", "claude"),
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
]


def find_claude(custom: str = "") -> Optional[str]:
    if custom:
        path = os.path.expanduser(custom)
        return path if os.access(path, os.X_OK) else None
    found = shutil.which("claude")
    if found:
        return found
    for path in CANDIDATES:
        if os.access(path, os.X_OK):
            return path
    return None


class ClaudeRun:
    """One streamed reply. Callbacks fire on a worker thread."""

    def __init__(
        self,
        exe: str,
        system_prompt: str,
        prompt: str,
        cwd: str,
        model: str,
        on_delta: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.exe = exe
        self.system_prompt = system_prompt
        self.prompt = prompt
        self.cwd = cwd
        self.model = model
        self.on_delta = on_delta
        self.on_done = on_done
        self.on_error = on_error
        self.cancelled = False
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        threading.Thread(target=self._run, name="mn-claude", daemon=True).start()

    def cancel(self) -> None:
        self.cancelled = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def _args(self) -> list[str]:
        args = [
            self.exe,
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--system-prompt", self.system_prompt,
        ]
        if self.model:
            args += ["--model", self.model]
        return args

    def _run(self) -> None:
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(
            [os.path.dirname(self.exe), env.get("PATH", ""), "/usr/bin", "/bin"]
        )
        try:
            os.makedirs(self.cwd, exist_ok=True)
            self._proc = subprocess.Popen(
                self._args(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=env,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except Exception as exc:  # binary vanished, permissions, ...
            self.on_error(f"Couldn't start Claude Code: {exc}")
            return

        proc = self._proc
        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(self.prompt)
            proc.stdin.close()
        except Exception:
            pass

        got_text = False
        result_seen = False
        error_text = ""
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if self.cancelled:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                kind = event.get("type")
                if kind == "stream_event":
                    ev = event.get("event") or {}
                    delta = ev.get("delta") or {}
                    if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        text = delta.get("text") or ""
                        if text:
                            got_text = True
                            self.on_delta(text)
                elif kind == "result":
                    result_seen = True
                    if event.get("is_error"):
                        error_text = str(event.get("result") or "Claude Code reported an error.")
        except Exception as exc:
            error_text = error_text or f"Lost the connection to Claude Code: {exc}"

        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

        if self.cancelled:
            return
        if error_text:
            self.on_error(error_text)
            return
        if not result_seen and not got_text:
            stderr = ""
            try:
                stderr = (proc.stderr.read() if proc.stderr else "").strip()  # type: ignore[union-attr]
            except Exception:
                pass
            self.on_error(stderr.splitlines()[-1] if stderr else "Claude Code stopped without replying.")
            return
        self.on_done()
