#!/usr/bin/env bash
set -euo pipefail
out=${1:?请指定样片目录}
ffmpeg=${FFMPEG:-ffmpeg}
mkdir -p "$out"
"$ffmpeg" -hide_banner -loglevel error -y -f lavfi   -i 'color=red:s=640x360:r=24:d=2'   -vf "drawbox=x=320:y=0:w=320:h=180:color=lime:t=fill,drawbox=x=0:y=180:w=320:h=180:color=blue:t=fill,drawbox=x=320:y=180:w=320:h=180:color=yellow:t=fill,drawbox=x=288:y=148:w=64:h=64:color=white:t=fill:enable='gte(t,0.7)'"   -c:v libx264 -pix_fmt yuv420p -profile:v baseline "$out/rotate-0.mp4"
for angle in 90 180 270; do
  "$ffmpeg" -hide_banner -loglevel error -y -display_rotation:v:0 "$angle"     -i "$out/rotate-0.mp4" -map 0:v:0 -c copy "$out/rotate-$angle.mp4"
done

# 仅将首个解码帧置黑，保留方向正确的后续帧及白块。
"$ffmpeg" -hide_banner -loglevel error -y -i "$out/rotate-0.mp4" \
  -vf "drawbox=color=black:t=fill:enable='eq(n,0)'" -c:v libx264 -profile:v baseline \
  "$out/black-first.mp4"
