/* Ask AI panel: UI only. Python owns the conversation and talks to the
 * providers; this file renders it and reports what the user does. */
(function () {
  "use strict";

  var ICON = {
    compose:
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 8.5V13a1.5 1.5 0 0 1-1.5 1.5H3A1.5 1.5 0 0 1 1.5 13V4A1.5 1.5 0 0 1 3 2.5h4.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><path d="M12.2 1.8a1.2 1.2 0 0 1 1.7 1.7L8.2 9.2 6 9.9l.7-2.2z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
    close:
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
    send:
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13V3.5M3.8 7.6 8 3.4l4.2 4.2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    stop: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="4.5" y="4.5" width="7" height="7" rx="1.6" fill="currentColor"/></svg>',
    spark:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8c.5 4.6 2.6 6.7 7.2 7.2-4.6.5-6.7 2.6-7.2 7.2-.5-4.6-2.6-6.7-7.2-7.2 4.6-.5 6.7-2.6 7.2-7.2z" fill="currentColor"/><path d="M18.6 14.6c.2 2 1.1 2.9 3.1 3.1-2 .2-2.9 1.1-3.1 3.1-.2-2-1.1-2.9-3.1-3.1 2-.2 2.9-1.1 3.1-3.1z" fill="currentColor" opacity=".55"/></svg>',
    card:
      '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3.5" width="12" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5 7h6M5 9.5h3.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    warn:
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.2 14.3 13H1.7z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><path d="M8 6.3v3.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><circle cx="8" cy="11.4" r=".8" fill="currentColor"/></svg>',
    chevron:
      '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2.6 3.8 5 6.2l2.4-2.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    check:
      '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.4 5 8.8l4.6-5.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  };

  var SUGGEST = {
    question: ["Give me a hint", "What is this card asking?", "Explain the key term"],
    answer: ["Explain the answer", "Why is this right?", "Give me an example", "Help me remember it"],
    none: ["How does spaced repetition work?"],
  };

  var ctx = { state: "none", revealed: false, deck: "", shortcut: "", provider: null, providers: [] };
  var streaming = false;
  var starting = false;
  var buffer = "";
  var liveEl = null;
  var rafPending = false;
  var menuOpen = false;
  var els = {};

  function send(msg) {
    try {
      pycmd("mnai:" + JSON.stringify(msg));
    } catch (e) {}
  }

  function h(tag, cls, html) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (html != null) el.innerHTML = html;
    return el;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function current() {
    for (var i = 0; i < ctx.providers.length; i++) {
      if (ctx.providers[i].id === ctx.provider) return ctx.providers[i];
    }
    return null;
  }

  function currentName() {
    var p = current();
    return p ? p.name : "AI";
  }

  function ready() {
    var p = current();
    return !!(p && p.available);
  }

  // Small, safe Markdown: text is escaped first, then a few marks applied.
  function inline(s) {
    return s
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>")
      .replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  }

  function markdown(src) {
    var out = [];
    var parts = String(src).split(/```/);
    for (var p = 0; p < parts.length; p++) {
      if (p % 2 === 1) {
        var code = parts[p].replace(/^[a-zA-Z0-9_+-]*\n/, "");
        out.push("<pre><code>" + esc(code.replace(/\n$/, "")) + "</code></pre>");
        continue;
      }
      var lines = esc(parts[p]).split("\n");
      var list = null;
      var para = [];
      var flushPara = function () {
        if (para.length) out.push("<p>" + inline(para.join("<br>")) + "</p>");
        para = [];
      };
      var flushList = function () {
        if (list) out.push("<" + list.tag + ">" + list.items.join("") + "</" + list.tag + ">");
        list = null;
      };
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        var m;
        if (/^\s*$/.test(line)) {
          flushPara();
          flushList();
        } else if ((m = line.match(/^\s*#{1,6}\s+(.*)$/))) {
          flushPara();
          flushList();
          out.push("<h4>" + inline(m[1]) + "</h4>");
        } else if ((m = line.match(/^\s*[-*•]\s+(.*)$/)) || (m = line.match(/^\s*(\d+)[.)]\s+(.*)$/))) {
          flushPara();
          var ordered = m.length === 3;
          var tag = ordered ? "ol" : "ul";
          if (!list || list.tag !== tag) {
            flushList();
            list = { tag: tag, items: [] };
          }
          list.items.push("<li>" + inline(ordered ? m[2] : m[1]) + "</li>");
        } else {
          flushList();
          para.push(line);
        }
      }
      flushPara();
      flushList();
    }
    return out.join("");
  }

  // ── Layout ──────────────────────────────────────────────────────

  function build() {
    var root = document.getElementById("mn-ai");
    if (!root) return;

    var head = h("header", "ai-head");
    els.picker = h("button", "ai-picker");
    els.picker.setAttribute("aria-haspopup", "menu");
    els.picker.setAttribute("aria-expanded", "false");
    head.appendChild(els.picker);
    var actions = h("div", "ai-actions");
    els.newBtn = h("button", "ai-icon", ICON.compose);
    els.newBtn.title = "New conversation";
    els.newBtn.setAttribute("aria-label", "New conversation");
    els.closeBtn = h("button", "ai-icon", ICON.close);
    els.closeBtn.setAttribute("aria-label", "Close panel");
    actions.appendChild(els.newBtn);
    actions.appendChild(els.closeBtn);
    head.appendChild(actions);

    els.menu = h("div", "ai-menu");
    els.menu.setAttribute("role", "menu");
    els.menu.hidden = true;

    els.chip = h("div", "ai-context");

    els.thread = h("main", "ai-thread");
    els.thread.setAttribute("aria-live", "polite");

    var foot = h("footer", "ai-composer");
    var box = h("div", "ai-box");
    els.input = h("textarea", "ai-input");
    els.input.rows = 1;
    els.input.setAttribute("aria-label", "Message");
    els.sendBtn = h("button", "ai-send", ICON.send);
    els.sendBtn.setAttribute("aria-label", "Send");
    box.appendChild(els.input);
    box.appendChild(els.sendBtn);
    foot.appendChild(box);
    foot.appendChild(h("div", "ai-note", "AI can make mistakes. Check important facts."));

    root.appendChild(head);
    root.appendChild(els.menu);
    root.appendChild(els.chip);
    root.appendChild(els.thread);
    root.appendChild(foot);

    els.picker.addEventListener("click", function () {
      menuOpen ? closeMenu() : openMenu();
    });
    els.newBtn.addEventListener("click", function () {
      send({ type: "new" });
    });
    els.closeBtn.addEventListener("click", function () {
      send({ type: "close" });
    });
    els.sendBtn.addEventListener("click", function () {
      streaming ? send({ type: "stop" }) : submit();
    });
    els.input.addEventListener("input", function () {
      grow();
      updateSend();
    });
    els.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (!streaming) submit();
      } else if (e.key === "Escape") {
        els.input.blur();
      }
    });
    els.input.addEventListener("focus", function () {
      send({ type: "focus" });
    });
    els.input.addEventListener("blur", function () {
      send({ type: "blur" });
    });
    document.addEventListener("mousedown", function (e) {
      if (menuOpen && !els.menu.contains(e.target) && !els.picker.contains(e.target)) closeMenu();
    });
    els.menu.addEventListener("keydown", menuKeys);

    renderHeader();
    renderChip();
    renderEmpty();
    updateSend();
    send({ type: "ready" });
  }

  // ── Model picker: a pull-down anchored to the title ────────────

  function renderHeader() {
    var p = current();
    els.picker.innerHTML =
      '<span class="ai-picker-name">' + esc(p ? p.name : "Choose a model") + "</span>" + ICON.chevron;
    els.picker.title = starting ? "Starting Ollama…" : p ? p.detail : "";
  }

  function renderMenu() {
    els.menu.innerHTML = "";
    var group = null;
    ctx.providers.forEach(function (p) {
      if (p.group !== group) {
        group = p.group;
        els.menu.appendChild(h("div", "ai-menu-group", esc(group)));
      }
      var item = h("button", "ai-menu-item");
      item.setAttribute("role", "menuitemradio");
      item.setAttribute("aria-checked", p.id === ctx.provider ? "true" : "false");
      var detail = p.available ? p.detail : p.reason || p.detail;
      if (starting && p.id === "ollama:start") detail = "Starting…";
      item.innerHTML =
        '<span class="ai-menu-check">' + (p.id === ctx.provider ? ICON.check : "") + "</span>" +
        '<span class="ai-menu-text"><span class="ai-menu-name">' + esc(p.name) + "</span>" +
        '<span class="ai-menu-detail">' + esc(detail || "") + "</span></span>";
      if (!p.available || (starting && p.id === "ollama:start")) {
        item.disabled = true;
      } else {
        item.addEventListener("click", function () {
          send({ type: "select", id: p.id });
          if (p.kind !== "action") closeMenu();
        });
      }
      els.menu.appendChild(item);
    });
  }

  function openMenu() {
    send({ type: "refresh" });
    renderMenu();
    els.menu.hidden = false;
    menuOpen = true;
    els.picker.setAttribute("aria-expanded", "true");
    els.picker.classList.add("is-open");
    var first = els.menu.querySelector(".ai-menu-item[aria-checked=true]") || els.menu.querySelector(".ai-menu-item:not([disabled])");
    if (first) first.focus();
  }

  function closeMenu() {
    if (!menuOpen) return;
    menuOpen = false;
    els.menu.hidden = true;
    els.picker.setAttribute("aria-expanded", "false");
    els.picker.classList.remove("is-open");
  }

  function menuKeys(e) {
    var items = Array.prototype.slice.call(els.menu.querySelectorAll(".ai-menu-item:not([disabled])"));
    var i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      (items[i + 1] || items[0]).focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      (items[i - 1] || items[items.length - 1]).focus();
    } else if (e.key === "Escape") {
      closeMenu();
      els.picker.focus();
    }
  }

  // ── Thread ──────────────────────────────────────────────────────

  function grow() {
    var t = els.input;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 132) + "px";
  }

  function updateSend() {
    var empty = !els.input.value.trim();
    els.sendBtn.classList.toggle("is-stop", streaming);
    els.sendBtn.innerHTML = streaming ? ICON.stop : ICON.send;
    els.sendBtn.setAttribute("aria-label", streaming ? "Stop" : "Send");
    els.sendBtn.title = streaming ? "Stop" : "Send (Return)";
    els.sendBtn.disabled = !streaming && (empty || !ready());
  }

  function placeholder() {
    var name = currentName();
    if (ctx.state !== "card") return "Ask " + name + " anything…";
    return ctx.revealed ? "Ask " + name + " about this answer…" : "Ask " + name + " for a hint…";
  }

  function renderChip() {
    var text = ctx.state !== "card" ? "No card open" : ctx.revealed ? "Answer shown" : "Answer hidden — hints only";
    els.chip.innerHTML =
      '<span class="ai-chip">' + ICON.card + "<span>" + esc(text) + "</span></span>" +
      (ctx.state === "card" && ctx.deck ? '<span class="ai-deck">' + esc(ctx.deck) + "</span>" : "");
    els.input.placeholder = placeholder();
    els.closeBtn.title = "Close (" + (ctx.shortcut || "⌥⌘I") + ")";
  }

  function scrollNearBottom() {
    var t = els.thread;
    return t.scrollHeight - t.scrollTop - t.clientHeight < 48;
  }

  function scrollToEnd() {
    els.thread.scrollTop = els.thread.scrollHeight;
  }

  function renderEmpty() {
    els.thread.innerHTML = "";
    var empty = h("section", "ai-empty mn-in");
    empty.appendChild(h("div", "ai-mark", ICON.spark));
    var p = current();
    if (!ready()) {
      empty.appendChild(h("h2", "", p ? esc(p.name) + " isn't ready" : "Choose a model"));
      empty.appendChild(
        h("p", "", p && p.reason ? esc(p.reason) + ". Pick another model from the menu above." : "Pick Claude, ChatGPT, Gemini or a local model from the menu above.")
      );
      els.thread.appendChild(empty);
      return;
    }
    var name = esc(p.name);
    var title = ctx.state !== "card" ? "Ask " + name : ctx.revealed ? "Make it click" : "Stuck on this card?";
    var sub =
      ctx.state !== "card"
        ? "Start reviewing a deck to ask about a card. You can still ask general questions."
        : ctx.revealed
        ? "Ask why the answer is what it is, or for an example."
        : name + " can see the question, not the answer, so you'll get hints first.";
    empty.appendChild(h("h2", "", title));
    empty.appendChild(h("p", "", sub));
    var list = h("div", "ai-suggest");
    var items = SUGGEST[ctx.state !== "card" ? "none" : ctx.revealed ? "answer" : "question"];
    items.forEach(function (label) {
      var b = h("button", "ai-chipbtn", esc(label));
      b.addEventListener("click", function () {
        if (!streaming && ready()) submit(label);
      });
      list.appendChild(b);
    });
    empty.appendChild(list);
    els.thread.appendChild(empty);
  }

  function clearEmpty() {
    var empty = els.thread.querySelector(".ai-empty");
    if (empty) empty.remove();
  }

  function addUser(text) {
    clearEmpty();
    var row = h("div", "ai-msg ai-user mn-in");
    row.appendChild(h("div", "ai-bubble", esc(text).replace(/\n/g, "<br>")));
    els.thread.appendChild(row);
    scrollToEnd();
  }

  function startReply() {
    clearEmpty();
    var row = h("div", "ai-msg ai-reply mn-in");
    row.appendChild(h("div", "ai-who", esc(currentName())));
    var body = h("div", "ai-text");
    body.appendChild(h("div", "ai-typing", "<i></i><i></i><i></i>"));
    row.appendChild(body);
    els.thread.appendChild(row);
    liveEl = body;
    buffer = "";
    scrollToEnd();
  }

  function paint() {
    rafPending = false;
    if (!liveEl) return;
    var stick = scrollNearBottom();
    liveEl.innerHTML = markdown(buffer) + (streaming ? '<span class="ai-caret"></span>' : "");
    if (stick) scrollToEnd();
  }

  function submit(text) {
    var value = (text != null ? text : els.input.value).trim();
    if (!value || streaming || !ready()) return;
    els.input.value = "";
    grow();
    addUser(value);
    streaming = true;
    startReply();
    updateSend();
    send({ type: "send", text: value });
  }

  function removeLive() {
    if (liveEl && liveEl.parentNode) liveEl.parentNode.remove();
    liveEl = null;
  }

  // ── API called from Python ─────────────────────────────────────

  window.mnAI = {
    setContext: function (next) {
      var before = ctx.state + "|" + ctx.revealed + "|" + ctx.provider + "|" + ready();
      ctx = next;
      if (!els.chip) return;
      renderHeader();
      renderChip();
      if (menuOpen) renderMenu();
      var after = ctx.state + "|" + ctx.revealed + "|" + ctx.provider + "|" + ready();
      if (before !== after && els.thread.querySelector(".ai-empty")) renderEmpty();
      updateSend();
    },
    setStarting: function (on) {
      starting = on;
      if (!els.picker) return;
      renderHeader();
      if (menuOpen) renderMenu();
    },
    reset: function () {
      streaming = false;
      liveEl = null;
      buffer = "";
      if (!els.thread) return;
      renderEmpty();
      updateSend();
    },
    delta: function (chunk) {
      if (!liveEl) startReply();
      buffer += chunk;
      if (!rafPending) {
        rafPending = true;
        requestAnimationFrame(paint);
      }
    },
    done: function (stopped) {
      streaming = false;
      if (liveEl) {
        if (!buffer) {
          removeLive();
        } else {
          paint();
          if (stopped) liveEl.appendChild(h("div", "ai-stopped", "Stopped"));
        }
      }
      liveEl = null;
      updateSend();
    },
    error: function (message, kind, hint) {
      streaming = false;
      if (!buffer) removeLive();
      liveEl = null;
      var name = esc(currentName());
      var title = kind === "signin" ? "Sign in to use " + name : kind === "missing" ? name + " isn't available" : name + " couldn't answer";
      var card = h("div", "ai-error mn-in");
      card.innerHTML =
        '<div class="ai-error-icon">' + ICON.warn + "</div><div><strong>" + title + "</strong><p>" +
        (hint || esc(message)) + "</p></div>";
      if (kind === "signin") {
        var signIn = h("button", "ai-error-action", "Sign In\u2026");
        signIn.type = "button";
        signIn.addEventListener("click", function () {
          send({ type: "signin" });
        });
        card.lastChild.appendChild(signIn);
      }
      clearEmpty();
      els.thread.appendChild(card);
      scrollToEnd();
      updateSend();
    },
    focusComposer: function () {
      if (els.input) els.input.focus();
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
