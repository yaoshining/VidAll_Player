#!/usr/bin/env bash
# T061：验证构件必须有可串联的成功路径和完整的失败闭合证据。
set -euo pipefail
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly CREATE="$ROOT/scripts/release/create-verification-artifact.sh"
fail() { echo "测试失败：$*" >&2; exit 1; }
expect_fail() { local label="$1"; shift; if "$@" >/dev/null 2>&1; then fail "$label 应失败"; fi; }
main() {
  local temp="$({ mktemp -d; })"; trap 'rm -rf "${temp:-}"' EXIT
  cat > "$temp/lock.json" <<'JSON'
{"schemaVersion":3,"releaseVersion":"0.1.0","sources":{"mpv":{"repository":"https://example.test/mpv","tag":"v0.1.0","commit":"1111111111111111111111111111111111111111","license":"MIT"}},"licensePolicy":{"releaseRequiresReview":[],"noticeRequired":true,"sourceOfferRequired":true}}
JSON
  printf 'not-an-elf-but-sha-input' > "$temp/libmpv.so"
  cat > "$temp/audit.sh" <<'SH'
#!/usr/bin/env bash
set -eu; output=''; while [ "$#" -gt 0 ]; do [ "$1" = --output ] && { output="$2"; shift 2; } || shift; done
printf '{"status":"passed"}\n' > "$output"
SH
  chmod +x "$temp/audit.sh"
  printf '{"status":"passed"}\n' > "$temp/har.json"
  printf '{"status":"passed"}\n' > "$temp/smoke.json"
  env VERIFICATION_ELF_AUDIT_SCRIPT="$temp/audit.sh" "$CREATE" --lock "$temp/lock.json" --elf "$temp/libmpv.so" --output "$temp/verification.json" --internal-load "$temp/har.json" --consumer-smoke "$temp/smoke.json"
  python3 - "$temp/verification.json" <<'PY'
import json, sys
m=json.load(open(sys.argv[1])); assert m['artifactType']=='verification' and m['status']=='verified'
assert all(m['evidence'][name]['valid'] for name in ('sbom','licenses','elfAudit','harInclusion','consumerSmoke'))
PY
  "$ROOT/scripts/release/create-candidate.sh" "$temp/verification.json" "$temp/candidate.json" >/dev/null
  expect_fail '缺少 ELF 输入' "$CREATE" --lock "$temp/lock.json" --output "$temp/out.json"
  expect_fail '缺少内部装入证明' env VERIFICATION_ELF_AUDIT_SCRIPT="$temp/audit.sh" "$CREATE" --lock "$temp/lock.json" --elf "$temp/libmpv.so" --output "$temp/out.json" --internal-load "$temp/no-har.json" --consumer-smoke "$temp/smoke.json"
  expect_fail '缺少 consumer-smoke 证明' env VERIFICATION_ELF_AUDIT_SCRIPT="$temp/audit.sh" "$CREATE" --lock "$temp/lock.json" --elf "$temp/libmpv.so" --output "$temp/out.json" --internal-load "$temp/har.json" --consumer-smoke "$temp/no-smoke.json"
  cat > "$temp/failed-audit.sh" <<'SH'
#!/usr/bin/env bash
set -eu; output=''; while [ "$#" -gt 0 ]; do [ "$1" = --output ] && { output="$2"; shift 2; } || shift; done
printf '{"status":"failed"}\n' > "$output"
SH
  chmod +x "$temp/failed-audit.sh"
  expect_fail 'ELF 审计失败' env VERIFICATION_ELF_AUDIT_SCRIPT="$temp/failed-audit.sh" "$CREATE" --lock "$temp/lock.json" --elf "$temp/libmpv.so" --output "$temp/out.json" --internal-load "$temp/har.json" --consumer-smoke "$temp/smoke.json"
  echo 'T061：验证构件 schema、候选串联与失败闭合测试通过。'
}
main "$@"
