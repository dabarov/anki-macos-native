/* macOS Native for Anki — small DOM touches the stylesheet can't do alone.
 * Runs in <head>; everything is optional polish, so every step is guarded. */
(function () {
  "use strict";

  var root = document.documentElement;
  var screen = root.dataset.mn;
  if (!screen) return;

  // 1. Entrance motion, only when arriving from a different screen.
  //    Anki redraws the deck list after a collapse, a sync or a rename;
  //    re-animating on each of those would be noise, not feedback.
  var MAIN = { decks: 1, overview: 1, reviewer: 1 };
  if (MAIN[screen]) {
    var last = null;
    try {
      last = sessionStorage.getItem("mn-last-screen");
      sessionStorage.setItem("mn-last-screen", screen);
    } catch (e) {}
    var wantsMotion = root.dataset.mnMotion !== "off";
    if (wantsMotion && screen !== "reviewer" && last !== null && last !== screen) {
      root.setAttribute("data-mn-enter", "");
      // Drop the flag once settled so later DOM inserts don't animate.
      setTimeout(function () {
        root.removeAttribute("data-mn-enter");
      }, 900);
    }
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  // 2. Deck list: Anki marks collapse state with "+" / "-" text. Turn it
  //    into a data attribute for the chevron and proper ARIA for VoiceOver.
  function markDisclosures(scope) {
    var links = (scope || document).querySelectorAll("a.collapse");
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var t = (a.textContent || "").trim();
      if (t !== "+" && t !== "-") continue;
      var collapsed = t === "+";
      a.setAttribute("data-mn-state", collapsed ? "collapsed" : "expanded");
      a.setAttribute("role", "button");
      a.setAttribute("aria-expanded", collapsed ? "false" : "true");
      a.setAttribute("aria-label", collapsed ? "Expand" : "Collapse");
    }
  }

  // 3. Overview: "New:" → "New". The tile layout supplies the separation.
  function tidyOverviewLabels() {
    var cells = document.querySelectorAll("center table table td:first-child");
    for (var i = 0; i < cells.length; i++) {
      var c = cells[i];
      if (c.children.length === 0) {
        c.textContent = c.textContent.replace(/[:：]\s*$/, "");
      }
    }
    // A zero shouldn't shout in red or green; grey it like the deck list does.
    var counts = document.querySelectorAll(
      "center table table .new-count, center table table .learn-count, center table table .review-count"
    );
    for (var j = 0; j < counts.length; j++) {
      if ((counts[j].textContent || "").trim() === "0") counts[j].classList.add("mn-zero");
    }
  }

  ready(function () {
    if (screen === "decks") {
      markDisclosures();
      try {
        new MutationObserver(function () {
          markDisclosures();
        }).observe(document.body, { childList: true, subtree: true });
      } catch (e) {}
    } else if (screen === "overview") {
      tidyOverviewLabels();
    }
  });
})();
