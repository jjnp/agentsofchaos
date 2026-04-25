#!/usr/bin/env bash
# Render a real-time gif from the latest demo recording.
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
# default global palette ffmpeg uses without it. Playback is real-time
# (no setpts speed-up) and fps is held at 8 so the total frame count
# stays close to what the previous 2x/15fps render produced — that
# keeps the file size in the same ballpark even though the gif is now
# twice as long. 8fps is fine for a UI walkthrough dominated by typing
# and pauses; bumping it higher inflates filesize fast.
palette="$(mktemp --suffix=.png)"
filters="fps=8,scale=960:-1:flags=lanczos"

ffmpeg -y -loglevel error -i "${src}" -vf "${filters},palettegen=stats_mode=diff" "${palette}"
ffmpeg -y -loglevel error -i "${src}" -i "${palette}" \
  -lavfi "${filters} [v]; [v][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "${dest}"

rm -f "${palette}"

ls -lh "${dest}"
