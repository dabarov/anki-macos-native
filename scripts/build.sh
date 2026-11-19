#!/bin/sh
# Builds dist/macos_native_anki.ankiaddon: double-click it (or Tools → Add-ons →
# Install from file…) on any Mac to install or update the add-on.
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
out="dist/macos_native_anki.ankiaddon"
rm -f "$out"
zip -rq "$out" . \
  -x '.git/*' '.gitignore' 'dist/*' 'scripts/*' 'docs/*' \
     'meta.json' 'user_files/claude-workdir/*' '*__pycache__*' '*.pyc' '*.DS_Store'
echo "Built $out ($(du -h "$out" | cut -f1))"
