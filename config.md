**accent** — `"system"` follows the accent colour in System Settings → Appearance (read when Anki starts). Use a hex colour such as `"#5e5ce6"` to pick your own.

**motion** — `true` lets screens settle in with a soft spring and buttons press in when clicked. `false` turns entrance motion off. Motion also turns itself off when macOS "Reduce motion" or Anki's own "Reduce motion" setting is on.

**card_font**: `"system"` shows cards that still use Anki's stock Arial in the macOS system font, so they match the rest of the window. This is display only: your note types aren't changed, and cards with a font you chose keep it. Use `"template"` to show exactly what the card's CSS says.

**ai_model**: the model used by the Ask Claude panel. Leave it empty (`""`) to use Claude Code's default, or name one, for example `"claude-opus-5-5"`, `"claude-sonnet-5-5"` or `"claude-haiku-5-5"`.

**claude_path**: where Claude Code is installed. Leave it empty to find it automatically (PATH, `~/.local/bin`, Homebrew).

Restart Anki after changing these.
