**accent**: `"system"` follows the accent colour in System Settings → Appearance (read when Anki starts). Use a hex colour such as `"#5e5ce6"` to pick your own.

**motion**: `true` lets screens settle in with a soft spring and buttons press in when clicked. `false` turns entrance motion off. Motion also turns itself off when macOS "Reduce motion" or Anki's own "Reduce motion" setting is on.

**card_font**: `"system"` shows cards that still use Anki's stock Arial in the macOS system font, so they match the rest of the window. This is display only: your note types aren't changed, and cards with a font you chose keep it. Use `"template"` to show exactly what the card's CSS says.

**Ask AI panel.** Pick the model from the panel's title. These settings only fine-tune it:

- **claude_model**: empty uses Claude Code's default, or name one such as `"claude-sonnet-5-5"`.
- **codex_model**: the ChatGPT model. Empty uses the first model Codex lists for your account.
- **gemini_model**: empty uses the Gemini CLI default.
- **ollama_url**: where Ollama is listening, usually `"http://127.0.0.1:11434"`.
- **claude_path**, **codex_path**, **gemini_path**: where each CLI is installed. Leave empty to find them automatically.

Restart Anki after changing these.
