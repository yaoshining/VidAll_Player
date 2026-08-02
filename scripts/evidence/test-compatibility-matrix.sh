#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
validator="$root/scripts/evidence/validate-evidence.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/valid.json" <<'JSON'
{"schemaVersion":1,"status":"blocked","matrix":{"lifecycle":{"status":"已构建待验证","device":"","sample":"","knownLimitations":"需要 ARM64 TV 真机证据","evidenceRef":""}}}
JSON
"$validator" --input "$tmp/valid.json"

cat > "$tmp/invalid.json" <<'JSON'
{"schemaVersion":1,"status":"blocked","matrix":{"lifecycle":{"status":"已支持"}}}
JSON
if "$validator" --input "$tmp/invalid.json" >/dev/null 2>&1; then
  echo '能力矩阵错误地接受了非三态结论' >&2
  exit 1
fi

cat > "$tmp/unverified-passed.json" <<'JSON'
{"schemaVersion":1,"status":"passed","recordedAt":"2026-08-02T00:00:00Z","matrix":{"lifecycle":{"status":"已构建待验证","knownLimitations":"需要 ARM64 TV 真机证据"}}}
JSON
if "$validator" --input "$tmp/unverified-passed.json" >/dev/null 2>&1; then
  echo '能力矩阵错误地接受了包含未验证条目的通过状态' >&2
  exit 1
fi

echo '兼容矩阵测试通过'
