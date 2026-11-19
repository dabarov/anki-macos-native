#!/bin/sh
# For editing the add-on on this Mac: links this folder into Anki's add-ons
# folder, so changes here apply the next time Anki starts.
# (To just use the add-on, install the .ankiaddon file from Releases instead.)
set -eu
repo="$(cd "$(dirname "$0")/.." && pwd)"
addons="$HOME/Library/Application Support/Anki2/addons21"
target="$addons/macos_native_anki"
mkdir -p "$addons"
if [ -e "$target" ] && [ ! -L "$target" ]; then
  echo "A real folder is already installed at:"
  echo "  $target"
  echo "Remove it in Anki (Tools → Add-ons → Delete) first, then run this again."
  exit 1
fi
ln -sfn "$repo" "$target"
echo "Linked $target -> $repo"
echo "Restart Anki to load it."
