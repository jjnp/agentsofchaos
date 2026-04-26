#!/usr/bin/env bash
# Render a 4x-speed gif from the latest demo recording.
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
# default global palette ffmpeg uses without it. The recording drives a
# real LLM through three runs + a merge so wall clock is ~10–15 min;
# we speed the gif up 4x (`setpts=PTS/4`) and run at 6fps to keep the
# file in the same ballpark as the noop-runtime version. Scale 960px
# wide so the inspector text stays legible.
palette="$(mktemp --suffix=.png)"
filters="setpts=PTS/3,fps=6,scale=720:-1:flags=lanczos"

ffmpeg -y -loglevel error -i "${src}" -vf "${filters},palettegen=stats_mode=diff" "${palette}"
# `-final_delay 300` parks the gif on its last frame for 3 seconds
# before looping. The value is in centiseconds and lives in the GIF
# Graphic Control Extension's per-frame delay field — pure metadata,
# zero filesize impact (one uint16 instead of zero). Gives a viewer
# time to read the integrated diff before the recording loops back
# to the project-open frame.
ffmpeg -y -loglevel error -i "${src}" -i "${palette}" \
  -lavfi "${filters} [v]; [v][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -final_delay 300 \
  "${dest}"

rm -f "${palette}"

ls -lh "${dest}"
