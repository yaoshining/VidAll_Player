#!/usr/bin/env bash
set -euo pipefail

output=''
device=''
iterations=100
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) output="$2"; shift 2 ;;
    --device) device="$2"; shift 2 ;;
    --iterations) iterations="$2"; shift 2 ;;
    *) echo '用法：write-arm64-tv-gate-template.sh --device <serial> --output <evidence.json> [--iterations 100]' >&2; exit 2 ;;
  esac
done
[ -n "$output" ] || { echo '缺少 --output' >&2; exit 2; }
[ -n "$device" ] || { echo '缺少 --device；禁止伪造 ARM64 TV 证据' >&2; exit 2; }
case "$iterations" in ''|*[!0-9]*) echo 'iterations 必须是正整数' >&2; exit 2 ;; esac
[ "$iterations" -ge 100 ] || { echo '生命周期门禁至少需要 100 次' >&2; exit 2; }

escaped_device=$(printf '%s' "$device" | sed 's/\\/\\\\/g; s/"/\\"/g')
mkdir -p "$(dirname "$output")"
cat > "$output" <<JSON
{
  "schemaVersion": 1,
  "status": "blocked",
  "requiredEvidence": ["device", "apiLevels", "lifecycleIterations", "crashLog", "deadlockCheck", "resourceCheck"],
  "reason": "脚本已就绪，但必须在连接的 ARM64 API 22 TV 上执行并人工归档真实日志；本次未写入通过结论。",
  "requestedDevice": "$escaped_device",
  "requiredIterations": $iterations,
  "scenarios": ["source-switch", "remote-focus-back", "background-foreground", "network-recovery", "repeated-release"]
}
JSON
printf 'ARM64 TV 门禁未执行：已写入阻断模板 %s\n' "$output"
