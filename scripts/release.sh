#!/bin/sh
# One-command release.
#
#   scripts/release.sh            # next patch version (1.0.0 → 1.0.1)
#   scripts/release.sh minor      # 1.0.0 → 1.1.0
#   scripts/release.sh major      # 1.0.0 → 2.0.0
#   scripts/release.sh 1.4.2      # an exact version
#   scripts/release.sh minor --dry-run   # show what would happen, change nothing
#
# Bumps the version in manifest.json, commits and tags it, builds the
# .ankiaddon, pushes, and publishes a GitHub release with notes grouped from
# the conventional commits since the last tag.
set -eu
cd "$(dirname "$0")/.."

bump="patch"
dry_run=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    patch|minor|major) bump="$arg" ;;
    [0-9]*.[0-9]*.[0-9]*) bump="$arg" ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "✗ $*" >&2; exit 1; }
# In a dry run, repo-state problems are reported but don't stop the preview.
check() { if [ "$dry_run" = 1 ]; then echo "⚠ $*" >&2; else fail "$*"; fi; }

command -v gh >/dev/null || fail "GitHub CLI (gh) is not installed."
gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not signed in. Run: gh auth login"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || check "Releases are made from main."
[ -z "$(git status --porcelain)" ] || check "Commit or stash your changes first."
git fetch --quiet --tags origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || check "main is not in sync with origin/main. Pull or push first."

current="$(python3 -c 'import json;print(json.load(open("manifest.json"))["human_version"])')"
next="$(python3 - "$current" "$bump" <<'EOF'
import sys
major, minor, patch = (int(x) for x in sys.argv[1].split("."))
bump = sys.argv[2]
if bump == "major": print(f"{major + 1}.0.0")
elif bump == "minor": print(f"{major}.{minor + 1}.0")
elif bump == "patch": print(f"{major}.{minor}.{patch + 1}")
else: print(bump)
EOF
)"
tag="v$next"
git rev-parse -q --verify "refs/tags/$tag" >/dev/null && fail "Tag $tag already exists."

last_tag="$(git describe --tags --abbrev=0 2>/dev/null || true)"
range="${last_tag:+$last_tag..}HEAD"
[ -n "$(git log --format=%H "$range")" ] || fail "No commits since $last_tag. Nothing to release."

notes="$(mktemp)"
trap 'rm -f "$notes"' EXIT
git log --format='%s' "$range" | python3 - "$tag" "$last_tag" > "$notes" <<'EOF'
import re, sys
tag, last = sys.argv[1], sys.argv[2]
groups = {"feat": "Features", "fix": "Fixes", "perf": "Performance"}
out = {title: [] for title in [*groups.values(), "Other changes"]}
for line in sys.stdin.read().splitlines():
    m = re.match(r"^(\w+)(\([^)]*\))?(!)?:\s*(.+)$", line)
    if not m:
        out["Other changes"].append(line)
        continue
    kind, scope, _, text = m.groups()
    if kind == "chore" and scope == "(release)":
        continue
    label = f"**{scope[1:-1]}:** {text}" if scope else text
    out[groups.get(kind, "Other changes")].append(label)
print("**Install:** download `macos_native_anki.ankiaddon` below, double-click it, then restart Anki.\n")
for title, items in out.items():
    if items:
        print(f"### {title}")
        print("\n".join(f"- {i}" for i in items) + "\n")
if last:
    print(f"Full changes: {last}...{tag}")
EOF

echo "Release $current → $next ($tag)"
echo "────────────────────────────────"
cat "$notes"
echo "────────────────────────────────"

if [ "$dry_run" = 1 ]; then
  ./scripts/build.sh
  echo "Dry run: nothing was committed, tagged, pushed or published."
  exit 0
fi

python3 - "$next" <<'EOF'
import json, sys, time
with open("manifest.json") as f:
    m = json.load(f)
m["human_version"] = sys.argv[1]
m["mod"] = int(time.time())
with open("manifest.json", "w") as f:
    json.dump(m, f, indent=4)
    f.write("\n")
EOF

git add manifest.json
git commit --quiet -m "chore(release): $tag"
git tag -a "$tag" -m "$tag"
./scripts/build.sh
git push --quiet origin main
git push --quiet origin "$tag"
gh release create "$tag" dist/macos_native_anki.ankiaddon --title "$tag" --notes-file "$notes"
echo "✓ Released $tag"
