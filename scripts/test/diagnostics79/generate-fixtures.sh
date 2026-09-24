#!/usr/bin/env bash
# 合成无私有信息的 90 秒双音轨 / 无音轨 / 无视频轨样本。
set -euo pipefail
OUT="${1:-/tmp/diagnostics79-fixtures}"
mkdir -p "$OUT"
ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=640x360:rate=25 \
  -f lavfi -i sine=frequency=440:sample_rate=48000 -f lavfi -i sine=frequency=880:sample_rate=48000 \
  -t 90 -map 0:v -map 1:a -map 2:a -c:v libx264 -preset ultrafast -crf 34 -pix_fmt yuv420p \
  -c:a aac -ac:a:0 2 -ac:a:1 1 -movflags +faststart -y "$OUT/diagnostics79-dual.mp4"
ffmpeg -hide_banner -loglevel error -i "$OUT/diagnostics79-dual.mp4" -t 12 -an -vf scale=320:180 \
  -c:v libx264 -preset ultrafast -crf 34 -y "$OUT/diagnostics79-silent.mp4"
ffmpeg -hide_banner -loglevel error -i "$OUT/diagnostics79-dual.mp4" -t 12 -vn -c:a copy -y "$OUT/diagnostics79-audio.m4a"
