"""Chat providers for the side panel.

Each provider answers through something already on this Mac, so no API keys
live in Anki:

  claude   Claude Code CLI (your Claude sign-in)
  chatgpt  Codex CLI, bundled with ChatGPT.app (your ChatGPT sign-in)
  gemini   Gemini CLI (your Google sign-in)
  ollama   any model in a local Ollama install

Every run streams text through on_delta and finishes with exactly one of
on_done / on_error. Callbacks fire on a worker thread.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from typing import Callable, Optional

from .claude_cli import ClaudeRun, find_claude

HOME = os.path.expanduser("~")
OLLAMA_URL = "http://127.0.0.1:11434"

Callback = Callable[..., None]


def _find(name: str, custom: str, extra: list[str]) -> Optional[str]:
    if custom:
        path = os.path.expanduser(custom)
        return path if os.access(path, os.X_OK) else None
    found = shutil.which(name)
    if found:
        return found
    for path in extra:
        if os.access(path, os.X_OK):
            return path
    return None


def find_codex(custom: str = "") -> Optional[str]:
    return _find("codex", custom, [
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
        os.path.join(HOME, ".local", "bin", "codex"),
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
    ])


def find_gemini(custom: str = "") -> Optional[str]:
    return _find("gemini", custom, [
        os.path.join(HOME, ".local", "bin", "gemini"),
        os.path.join(HOME, ".npm-global", "bin", "gemini"),
        "/opt/homebrew/bin/gemini",
        "/usr/local/bin/gemini",
    ])


def ollama_installed() -> bool:
    return any(
        os.path.exists(p)
        for p in ("/Applications/Ollama.app", "/usr/local/bin/ollama", "/opt/homebrew/bin/ollama")
    ) or bool(shutil.which("ollama"))


def codex_default_model() -> tuple[str, str]:
    """First model Codex lists for this account, as (slug, display name)."""
    try:
        with open(os.path.join(HOME, ".codex", "models_cache.json")) as f:
            data = json.load(f)
        models = data.get("models", []) if isinstance(data, dict) else data
        listed = [m for m in models if isinstance(m, dict) and m.get("visibility") == "list"]
        listed.sort(key=lambda m: m.get("priority", 1e9))
        if listed:
            return listed[0].get("slug", ""), listed[0].get("display_name", "")
    except Exception:
        pass
    return "", ""


def ollama_models(url: str) -> Optional[list[dict]]:
    """Installed Ollama models, or None if the server isn't reachable."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=0.8) as resp:
            data = json.load(resp)
    except Exception:
        return None
    return data.get("models", [])


def start_ollama() -> None:
    if sys.platform == "darwin" and os.path.exists("/Applications/Ollama.app"):
        subprocess.Popen(["open", "-a", "Ollama"])
    else:
        exe = shutil.which("ollama") or "/usr/local/bin/ollama"
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── Sign-in ─────────────────────────────────────────────────────────

_SIGN_IN = {
    "claude": ("Claude Code", find_claude, "claude_path", ["auth", "login"], ""),
    "codex": ("ChatGPT (Codex)", find_codex, "codex_path", ["login"], ""),
    "gemini": ("Gemini", find_gemini, "gemini_path", [],
               "Sign in when Gemini asks, then type /quit."),
}


def can_sign_in(kind: str) -> bool:
    return kind in _SIGN_IN


def open_sign_in(kind: str, cfg: dict, workdir: str) -> None:
    """Open Terminal running the assistant's own sign-in command.

    The credentials go straight to the CLI; Anki never sees them.
    """
    name, finder, key, args, note = _SIGN_IN[kind]
    exe = finder(cfg.get(key, ""))
    if not exe:
        raise RuntimeError(f"{name} isn't installed")
    lines = [
        "#!/bin/zsh",
        "clear",
        f"echo {shlex.quote(f'Signing in to {name} for Ask AI in Anki.')}",
    ]
    if note:
        lines.append(f"echo {shlex.quote(note)}")
    lines += [
        "echo",
        " ".join(shlex.quote(a) for a in [exe, *args]),
        "echo",
        "echo 'Done. Close this window and ask again in Anki.'",
    ]
    os.makedirs(workdir, exist_ok=True)
    script = os.path.join(workdir, f"sign-in-{kind}.command")
    with open(script, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(script, 0o700)
    subprocess.Popen(["open", "-a", "Terminal", script])


# ── Catalog ─────────────────────────────────────────────────────────

def catalog(cfg: dict) -> list[dict]:
    """Everything the picker can show, available or not, in display order."""
    items: list[dict] = []

    claude = find_claude(cfg.get("claude_path", ""))
    items.append({
        "id": "claude", "kind": "claude", "group": "Assistants",
        "name": "Claude", "detail": "Claude Code",
        "available": bool(claude), "reason": "" if claude else "Claude Code isn't installed",
    })

    codex = find_codex(cfg.get("codex_path", ""))
    slug, display = (cfg.get("codex_model") or "", "") if cfg.get("codex_model") else codex_default_model()
    items.append({
        "id": "chatgpt", "kind": "codex", "group": "Assistants",
        "name": "ChatGPT", "detail": f"Codex · {display or slug}" if (display or slug) else "Codex",
        "model": slug,
        "available": bool(codex), "reason": "" if codex else "Install ChatGPT or the Codex CLI",
    })

    gemini = find_gemini(cfg.get("gemini_path", ""))
    items.append({
        "id": "gemini", "kind": "gemini", "group": "Assistants",
        "name": "Gemini", "detail": "Gemini CLI",
        "model": cfg.get("gemini_model", ""),
        "available": bool(gemini), "reason": "" if gemini else "Gemini CLI isn't installed",
    })

    url = cfg.get("ollama_url") or OLLAMA_URL
    models = ollama_models(url)
    if models is None:
        if ollama_installed():
            items.append({
                "id": "ollama:start", "kind": "action", "group": "Ollama",
                "name": "Start Ollama", "detail": "Ollama isn't running", "available": True,
            })
    else:
        for m in models:
            name = m.get("name", "")
            base, _, tag = name.partition(":")
            cloud = bool(m.get("remote_host")) or tag.endswith("cloud")
            size = (m.get("details") or {}).get("parameter_size", "")
            detail = "Ollama · cloud" if cloud else f"Ollama · {size} · on this Mac" if size else "Ollama · on this Mac"
            items.append({
                "id": f"ollama:{name}", "kind": "ollama", "group": "Ollama",
                "name": base, "detail": detail, "model": name, "url": url,
                "available": True, "reason": "",
            })
        if not models:
            items.append({
                "id": "ollama:none", "kind": "action", "group": "Ollama",
                "name": "No models yet", "detail": "Run: ollama pull qwen3", "available": False,
            })
    return items


# ── Runs ────────────────────────────────────────────────────────────

class _Process:
    """Shared plumbing for CLI providers: start, cancel, PATH fix-up."""

    def __init__(self, on_delta: Callback, on_done: Callback, on_error: Callback) -> None:
        self.on_delta, self.on_done, self.on_error = on_delta, on_done, on_error
        self.cancelled = False
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        threading.Thread(target=self._guarded, daemon=True).start()

    def cancel(self) -> None:
        self.cancelled = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def _guarded(self) -> None:
        try:
            self._run()
        except Exception as exc:
            if not self.cancelled:
                self.on_error(str(exc))

    def _spawn(self, args: list[str], cwd: str, stdin_text: Optional[str]) -> subprocess.Popen:
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(
            [os.path.dirname(args[0]), "/opt/homebrew/bin", "/usr/local/bin", env.get("PATH", ""), "/usr/bin", "/bin"]
        )
        os.makedirs(cwd, exist_ok=True)
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        self.proc = proc
        if stdin_text is not None and proc.stdin:
            proc.stdin.write(stdin_text.encode("utf-8"))
            proc.stdin.close()
        return proc

    def _stderr_tail(self) -> str:
        try:
            text = (self.proc.stderr.read() if self.proc and self.proc.stderr else b"").decode("utf-8", "replace")
        except Exception:
            return ""
        lines = [l for l in text.strip().splitlines() if l.strip()]
        return lines[-1] if lines else ""

    def _run(self) -> None:
        raise NotImplementedError


# Card text comes from shared decks and can carry prompt injection, so Codex
# runs with every way to act switched off: no shell, no browser or computer
# use, no apps, plugins, MCP servers, hooks or web search. It can only reply.
CODEX_FEATURES_OFF = (
    "shell_tool", "unified_exec", "unified_exec_tty",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "browser_annotation_api", "in_app_browser", "computer_use",
    "apps", "plugins", "remote_plugin", "plugin_discovery_prefetch",
    "hooks", "image_generation", "view_image", "multi_agent",
    "skill_search", "tool_suggest", "goals", "in_app_local_automation",
    "sleep_tool", "workspace_dependencies", "code_mode_host",
)
CODEX_LOCKDOWN = (
    "-c", "mcp_servers={}",
    "-c", "notify=[]",
    "-c", 'web_search="disabled"',
    *[arg for name in CODEX_FEATURES_OFF for arg in ("-c", f"features.{name}=false")],
)


class CodexRun(_Process):
    """ChatGPT through `codex exec --json`, with no tools, in an empty folder."""

    def __init__(self, exe: str, model: str, prompt: str, cwd: str, **cb) -> None:
        super().__init__(**cb)
        self.args = [
            exe, "exec", "--json", "--skip-git-repo-check", "--ephemeral",
            "--sandbox", "read-only", "-C", cwd,
            "-c", 'model_reasoning_effort="low"',
            *CODEX_LOCKDOWN,
        ]
        if model:
            self.args += ["-m", model]
        self.args.append("-")
        self.prompt, self.cwd = prompt, cwd

    def _run(self) -> None:
        proc = self._spawn(self.args, self.cwd, self.prompt)
        sent_any, error = False, ""
        for raw in proc.stdout:  # type: ignore[union-attr]
            if self.cancelled:
                return
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            kind = event.get("type")
            item = event.get("item") or {}
            if kind == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text") or ""
                if text:
                    self.on_delta(("\n\n" if sent_any else "") + text)
                    sent_any = True
            elif kind == "error":
                error = event.get("message") or error
            elif kind == "turn.failed":
                error = (event.get("error") or {}).get("message") or error or "Codex couldn't finish."
        proc.wait()
        if self.cancelled:
            return
        if error and not sent_any:
            self.on_error(error)
        elif not sent_any:
            self.on_error(self._stderr_tail() or "Codex stopped without replying.")
        else:
            self.on_done()


class TextStreamRun(_Process):
    """A CLI that prints its reply to stdout (Gemini CLI)."""

    def __init__(self, args: list[str], cwd: str, **cb) -> None:
        super().__init__(**cb)
        self.args, self.cwd = args, cwd

    def _run(self) -> None:
        import codecs

        proc = self._spawn(self.args, self.cwd, None)
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        sent_any = False
        fd = proc.stdout.fileno()  # type: ignore[union-attr]
        while True:
            chunk = os.read(fd, 1024)
            if self.cancelled:
                return
            if not chunk:
                break
            text = decoder.decode(chunk)
            if text:
                sent_any = sent_any or bool(text.strip())
                self.on_delta(text)
        proc.wait()
        if self.cancelled:
            return
        if proc.returncode != 0 and not sent_any:
            self.on_error(self._stderr_tail() or f"Exited with code {proc.returncode}.")
        elif not sent_any:
            self.on_error(self._stderr_tail() or "No reply.")
        else:
            self.on_done()


class OllamaRun:
    """A local model through Ollama's streaming /api/chat."""

    def __init__(self, url: str, model: str, messages: list[dict], on_delta: Callback, on_done: Callback, on_error: Callback) -> None:
        self.url, self.model, self.messages = url.rstrip("/"), model, messages
        self.on_delta, self.on_done, self.on_error = on_delta, on_done, on_error
        self.cancelled = False
        self._resp = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self) -> None:
        self.cancelled = True
        try:
            if self._resp:
                self._resp.close()
        except Exception:
            pass

    def _request(self, think: Optional[bool]):
        body = {"model": self.model, "messages": self.messages, "stream": True}
        if think is not None:
            body["think"] = think  # skip slow hidden reasoning on thinking models
        req = urllib.request.Request(
            self.url + "/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=600)

    def _run(self) -> None:
        sent_any = False
        try:
            try:
                self._resp = self._request(False)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")
                if "think" not in detail:
                    raise RuntimeError(_ollama_error(detail)) from None
                self._resp = self._request(None)  # model can't toggle thinking
            for raw in self._resp:
                if self.cancelled:
                    return
                event = json.loads(raw)
                if event.get("error"):
                    raise RuntimeError(event["error"])
                text = (event.get("message") or {}).get("content") or ""
                if text:
                    sent_any = True
                    self.on_delta(text)
                if event.get("done"):
                    break
        except urllib.error.HTTPError as exc:
            if not self.cancelled:
                self.on_error(_ollama_error(exc.read().decode("utf-8", "replace")))
            return
        except Exception as exc:
            if not self.cancelled:
                self.on_error(str(exc) or "Ollama stopped responding.")
            return
        if self.cancelled:
            return
        self.on_done() if sent_any else self.on_error("The model returned an empty reply.")


def _ollama_error(body: str) -> str:
    try:
        return json.loads(body).get("error") or body
    except ValueError:
        return body or "Ollama returned an error."


def start_run(
    provider: dict,
    cfg: dict,
    system_prompt: str,
    transcript_prompt: str,
    chat_messages: list[dict],
    workdir: str,
    on_delta: Callback,
    on_done: Callback,
    on_error: Callback,
):
    cb = {"on_delta": on_delta, "on_done": on_done, "on_error": on_error}
    kind = provider["kind"]
    if kind == "claude":
        run = ClaudeRun(
            exe=find_claude(cfg.get("claude_path", "")) or "claude",
            system_prompt=system_prompt,
            prompt=transcript_prompt,
            cwd=workdir,
            model=str(cfg.get("claude_model") or cfg.get("ai_model") or ""),
            **cb,
        )
    elif kind == "codex":
        run = CodexRun(
            exe=find_codex(cfg.get("codex_path", "")) or "codex",
            model=provider.get("model", ""),
            prompt=f"{system_prompt}\n\n{transcript_prompt}",
            cwd=workdir,
            **cb,
        )
    elif kind == "gemini":
        args = [find_gemini(cfg.get("gemini_path", "")) or "gemini"]
        if provider.get("model"):
            args += ["-m", provider["model"]]
        args += ["-p", f"{system_prompt}\n\n{transcript_prompt}"]
        run = TextStreamRun(args, workdir, **cb)
    elif kind == "ollama":
        run = OllamaRun(
            provider.get("url") or OLLAMA_URL,
            provider["model"],
            [{"role": "system", "content": system_prompt}, *chat_messages],
            **cb,
        )
    else:
        raise ValueError(f"Unknown provider kind: {kind}")
    run.start()
    return run
