<p align="center">
  <img src="docs/logo.svg" width="128" height="128" alt="Anki macOS Native logo">
</p>

<h1 align="center">Anki macOS Native</h1>

<p align="center">
  <b>Make Anki feel like it shipped with macOS 26, and ask Claude about any card without leaving your review.</b>
</p>

<p align="center">
  <a href="https://github.com/dabarov/anki-macos-native/releases/latest/download/macos_native_anki.ankiaddon"><img src="https://img.shields.io/badge/download-.ankiaddon-0A60F0?style=flat-square" alt="Download"></a>
  <img src="https://img.shields.io/badge/Anki-26.09-1E88E5?style=flat-square" alt="Anki 26.09">
  <img src="https://img.shields.io/badge/macOS-26%20Tahoe-111111?style=flat-square&logo=apple" alt="macOS 26">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2EA44F?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <img src="docs/screenshots/ask-claude-answer.png" alt="Reviewing a card with the Ask Claude panel open" width="900">
</p>

## Before and after

| Stock Anki | With Anki macOS Native |
| --- | --- |
| ![Deck list before](docs/screenshots/before-decks.png) | ![Deck list after](docs/screenshots/after-decks.png) |
| ![Deck overview before](docs/screenshots/before-overview.png) | ![Deck overview after](docs/screenshots/after-overview.png) |
| ![Review before](docs/screenshots/before-answer.png) | ![Review after](docs/screenshots/after-answer.png) |

## What you get

### A main window that looks like a Mac app

- **San Francisco everywhere**, on the macOS type scale, with tracking set per size. Cards that still use Anki's stock Arial are shown in SF as well. Your note types are never edited, and cards with a font you picked keep it.
- **Your accent colour** from System Settings → Appearance, in light and dark mode.
- **A floating glass toolbar** in place of the flat strip of links.
- **An inset, grouped deck list** with rounded row highlights, chevrons for subdecks, an accent tint on the current deck, tabular counts and a "⋯" options button that appears on hover.
- **A deck overview** with a large title, count tiles and one clear Study Now button.
- **A calmer review bar.** Show Answer is the default button. Again / Hard / Good / Easy are tinted capsules, so colour tells them apart without four solid fills competing.
- **Motion that feels physical.** Buttons press in the moment you click and spring back on release. Screens settle in with a critically damped spring, only when you change screens.
- **Accessibility built in.** Reduce Motion (macOS or Anki) swaps motion for a short fade. Reduce Transparency turns glass solid. Increase Contrast strengthens edges and secondary text. VoiceOver labels the deck disclosure buttons.

<p align="center">
  <img src="docs/screenshots/dark-decks.png" alt="Deck list in dark mode" width="900">
</p>

### Ask Claude, right next to the card

<p align="center">
  <img src="docs/screenshots/ask-claude-hint.png" alt="Asking Claude for a hint while the answer is still hidden" width="900">
</p>

Stuck on a card? Open the panel with **Ask Claude** in the toolbar, Tools → Ask Claude, or **⌥⌘I**, and ask.

- **No spoilers.** While the answer is hidden, Claude sees only the question and gives hints. Once you reveal the answer, it explains it, gives examples or helps you remember it.
- **One conversation per card.** The next card starts fresh, and stepping out to the deck list and back keeps the conversation.
- **Typing is safe.** While the message field has focus, Anki's single-key review shortcuts (Space, Enter, 1–4, E, R, …) are paused, so typing "1" can't answer a card.
- **Replies stream in** as Claude writes them, and you can stop one at any time.

<p align="center">
  <img src="docs/screenshots/dark-ask-claude.png" alt="Ask Claude panel in dark mode" width="900">
</p>

## Install

1. Download **[macos_native_anki.ankiaddon](https://github.com/dabarov/anki-macos-native/releases/latest/download/macos_native_anki.ankiaddon)** from the latest release.
2. Double-click it. Anki opens and installs it. Or use Tools → Add-ons → Install from file….
3. Restart Anki.

To **update**, install the newer `.ankiaddon` the same way; your settings are kept. To **turn it off**, use Tools → Add-ons → macOS Native → Toggle Enabled.

### Setting up Ask Claude

The panel uses [Claude Code](https://claude.com/claude-code) on your Mac, so it works with your existing Claude plan and no API key is stored in Anki.

1. Install Claude Code.
2. Run `claude` in Terminal once and sign in.
3. Open the panel in Anki. If Claude Code can't be found, the panel says so. Point `claude_path` at it in the config if it lives somewhere unusual.

## Privacy

Ask Claude sends Claude Code the deck name, the card's question, the answer (only once you've revealed it) and the conversation for that card. Claude Code runs with its tools, MCP servers, skills and settings files switched off, so it can't read files or run commands. It can only reply to the text the panel sends. Nothing is sent until you ask a question.

## Configuration

Tools → Add-ons → macOS Native → Config. Restart Anki after changing a setting.

| Key | Default | What it does |
| --- | --- | --- |
| `accent` | `"system"` | Follows the macOS accent colour, or set a hex colour such as `"#5E5CE6"`. |
| `motion` | `true` | `false` turns off entrance motion. |
| `card_font` | `"system"` | Shows stock-Arial cards in SF. `"template"` shows exactly what the card's CSS says. |
| `ai_model` | `""` | Model for Ask Claude. Empty uses Claude Code's default. Try `"claude-sonnet-5-5"` for faster replies. |
| `claude_path` | `""` | Path to the `claude` binary, if it isn't found automatically. |

## Compatibility

Built and tested with **Anki 26.09** on **macOS 26 Tahoe**. The add-on only adds styles and a panel on top of Anki's own pages, and it never touches Anki's files or your collection's note types.

## Development

```bash
git clone https://github.com/dabarov/anki-macos-native.git
cd anki-macos-native
./scripts/install-dev.sh   # links the repo into Anki's add-ons folder
./scripts/build.sh         # builds dist/macos_native_anki.ankiaddon
```

| File | Purpose |
| --- | --- |
| `__init__.py` | Adds the theme to Anki's main-window pages, reads the accent colour, swaps stock Arial on cards |
| `web/macos.css`, `web/macos.js` | The theme. Every rule is scoped to `:root[data-mn="<screen>"]` |
| `ai_panel.py` | The Ask Claude dock: card context, per-card conversation, shortcut pausing |
| `claude_cli.py` | Streams one reply from Claude Code with tools off |
| `web/ai-panel.css`, `web/ai-panel.js` | The panel UI, using the same design tokens as the theme |
| `snapshot.py`, `audit.py` | Dev tools: `ANKI_MN_SNAPSHOT=<dir>` saves each screen as PNG; `ANKI_MN_AUDIT=<dir>` writes the computed fonts of every screen |

## Credits

Design guidance from Emil Kowalski's [apple-design](https://github.com/emilkowalski/skills/tree/main/skills/apple-design) skill and Apple's WWDC design talks.

Not affiliated with Anki, Apple or Anthropic.

## License

[MIT](LICENSE)
