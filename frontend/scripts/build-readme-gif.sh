#!/usr/bin/env bash
# Render a 2x-speed gif from the latest demo recording.
#
# Usage:
#   bash scripts/build-readme-gif.sh
#
# The output lands at docs/assets/demo.gif (relative to the repo root).
# Re-run after:  npx playwright test --config playwright.demo.config.ts
set -euo pipefail

cd "$(dirname "$0")/.."

src=$(ls -t test-results/demo-graph-native-demo-*/video.webm 2>/dev/null | head -1)
if [[ -z "${src}" ]]; then
  echo "no demo video found — run \`npx playwright test --config playwright.demo.config.ts\` first" >&2
  exit 1
fi

dest_dir="../docs/assets"
mkdir -p "${dest_dir}"
dest="${dest_dir}/demo.gif"

# Two-pass palette generation gives a much cleaner gif than the
# default global palette ffmpeg uses without it. Speed (2x) comes from
# `setpts=PTS/2`. Frame rate stays at 15 — gif compresses harder than
# webm and 30fps blows up the file size for little visible gain.
palette="$(mktemp --suffix=.png)"
filters="setpts=PTS/2,fps=15,scale=960:-1:flags=lanczos"

ffmpeg -y -loglevel error -i "${src}" -vf "${filters},palettegen=stats_mode=diff" "${palette}"
ffmpeg -y -loglevel error -i "${src}" -i "${palette}" \
  -lavfi "${filters} [v]; [v][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "${dest}"

rm -f "${palette}"

ls -lh "${dest}"
