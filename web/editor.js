/* Note editor: show fields that use Anki's stock Arial in the system font,
 * matching cards on the review screen (the card_font setting). Display only:
 * the field's font setting is untouched. Fields live in shadow roots, so the
 * override is added inside each one as fields appear. */
(function () {
  "use strict";

  // The editor page is built without the head snippet the other screens get,
  // so this script carries the theme settings in its own URL.
  var root = document.documentElement;
  var params = new URL((document.currentScript && document.currentScript.src) || location.href).searchParams;
  root.dataset.mn = "editor";
  if (params.get("light")) root.style.setProperty("--mn-accent-light", params.get("light"));
  if (params.get("dark")) root.style.setProperty("--mn-accent-dark", params.get("dark"));
  root.dataset.mnCardFont = params.get("font") || root.dataset.mnCardFont || "system";

  if (root.dataset.mnCardFont === "template") return;

  var MARK = "data-mn-font";
  var SYSTEM = '-apple-system, BlinkMacSystemFont, system-ui, sans-serif';

  function patch(host) {
    var root = host.shadowRoot;
    if (!root || root.querySelector("style[" + MARK + "]")) return;
    var styles = root.querySelectorAll("style");
    var stock = false;
    for (var i = 0; i < styles.length; i++) {
      if (/font-family:\s*["']?arial["']?\s*;/i.test(styles[i].textContent)) stock = true;
    }
    if (!stock) return;
    var style = document.createElement("style");
    style.setAttribute(MARK, "");
    style.textContent = "anki-editable { font-family: " + SYSTEM + " !important; }";
    root.appendChild(style);
  }

  function scan() {
    var hosts = document.querySelectorAll(".rich-text-editable");
    for (var i = 0; i < hosts.length; i++) patch(hosts[i]);
  }

  function start() {
    scan();
    // Fields are rebuilt when the note or note type changes; Anki also
    // rewrites a field's font style when settings change.
    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
