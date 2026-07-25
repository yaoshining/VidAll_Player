#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly LOCK_FILE="$PROJECT_ROOT/native/config/sources.lock.json"
readonly CONTROLLED_BUILD="$PROJECT_ROOT/native/scripts/build-libmpv-controlled.sh"
readonly MANIFEST_TOOL="$PROJECT_ROOT/native/scripts/generate-libmpv-manifest.sh"
readonly SBOM_TOOL="$PROJECT_ROOT/native/scripts/generate-sbom.sh"
readonly LICENSE_TOOL="$PROJECT_ROOT/native/scripts/audit-licenses.sh"
readonly ELF_AUDIT_TOOL="$PROJECT_ROOT/native/scripts/audit-libmpv-elf.sh"
readonly REPRODUCIBILITY_TOOL="$PROJECT_ROOT/native/scripts/verify-reproducible-artifacts.sh"
readonly NOTICE_TOOL="$PROJECT_ROOT/native/scripts/collect-licenses.sh"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

assert_json() {
  python3 - "$1" <<'PY'
import json
import sys
with open(sys.argv[1], encoding='utf-8') as f:
    json.load(f)
PY
}

main() {
  local temp_dir output_dir source_dir
  temp_dir="$(mktemp -d)"
  trap "rm -rf '$temp_dir'" EXIT
  output_dir="$temp_dir/output"
  source_dir="$temp_dir/source"

  test -x "$CONTROLLED_BUILD" || fail "缺少受控构建脚本"
  test -x "$MANIFEST_TOOL" || fail "缺少构建清单工具"
  test -x "$SBOM_TOOL" || fail "缺少 SBOM 工具"
  test -x "$LICENSE_TOOL" || fail "缺少许可证审计工具"
  test -x "$ELF_AUDIT_TOOL" || fail "缺少 ELF 审计工具"
  test -x "$REPRODUCIBILITY_TOOL" || fail "缺少可重复构建验证工具"
  test -x "$NOTICE_TOOL" || fail "缺少许可证收集工具"

  assert_json "$LOCK_FILE"
  python3 - "$LOCK_FILE" <<'PY'
import json
import re
import sys
lock = json.load(open(sys.argv[1], encoding='utf-8'))
required = {'mpv', 'ffmpeg', 'libass', 'dav1d', 'mbedtls', 'libplacebo', 'dovi_tools', 'freetype', 'harfbuzz', 'fribidi', 'fontconfig', 'lua'}
sources = lock.get('sources', {})
missing = required - set(sources)
assert not missing, f'缺少锁定来源：{sorted(missing)}'
for name, value in sources.items():
    assert re.fullmatch(r'[0-9a-f]{40}', value.get('commit', '')), f'{name} 未锁定到 commit SHA'
PY

  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg"
  printf '%s\n' '--enable-static' '--disable-shared' '--enable-demuxer=dash' > "$source_dir/ffmpeg/configure-options.txt"
  printf '%s\n' '-Dgpl=false' '-Dohos=enabled' > "$source_dir/mpv/meson-options.txt"
  printf '%s\n' 'dash' 'hls' > "$source_dir/ffmpeg/demuxers.txt"
  printf '%s\n' 'https' 'http' > "$source_dir/ffmpeg/protocols.txt"
  printf '%s\n' 'h264' 'hevc' > "$source_dir/ffmpeg/decoders.txt"
  printf '%s\n' 'png' > "$source_dir/ffmpeg/encoders.txt"
  printf '%s\n' 'scale' > "$source_dir/ffmpeg/filters.txt"
  printf '%s\n' 'libc++.so' 'libhilog_ndk.z.so' > "$source_dir/dynamic-dependencies.txt"

  "$MANIFEST_TOOL" --lock "$LOCK_FILE" --source "$source_dir" --output "$output_dir/feature-manifest.json" --abi arm64-v8a --min-sdk 15 --build-time 0
  assert_json "$output_dir/feature-manifest.json"
  python3 - "$output_dir/feature-manifest.json" <<'PY'
import json
import sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
assert m['abi'] == 'arm64-v8a'
assert m['minSdk'] == 15
assert m['buildTime'] == '1970-01-01T00:00:00Z'
assert m['ffmpeg']['configureOptions'] == ['--enable-static', '--disable-shared', '--enable-demuxer=dash']
assert m['ffmpeg']['components']['demuxers'] == ['dash', 'hls']
assert m['mpv']['mesonOptions'] == ['-Dgpl=false', '-Dohos=enabled']
assert m['dynamicDependencies'] == ['libc++.so', 'libhilog_ndk.z.so']
PY

  "$SBOM_TOOL" --lock "$LOCK_FILE" --format spdx --output "$output_dir/sbom.spdx.json"
  "$SBOM_TOOL" --lock "$LOCK_FILE" --format cyclonedx --output "$output_dir/sbom.cdx.json"
  assert_json "$output_dir/sbom.spdx.json"
  assert_json "$output_dir/sbom.cdx.json"
  python3 - "$output_dir/sbom.spdx.json" "$output_dir/sbom.cdx.json" <<'PY'
import json
import sys
spdx = json.load(open(sys.argv[1], encoding='utf-8'))
cdx = json.load(open(sys.argv[2], encoding='utf-8'))
assert spdx['spdxVersion'] == 'SPDX-2.3'
assert any(p['name'] == 'ffmpeg' for p in spdx['packages'])
assert cdx['bomFormat'] == 'CycloneDX'
assert any(c['name'] == 'mpv' for c in cdx['components'])
PY

  "$LICENSE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/license-audit.json"
  "$NOTICE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/NOTICE"
  test -s "$output_dir/NOTICE" || fail '许可证 NOTICE 不得为空'
  assert_json "$output_dir/license-audit.json"
  python3 - "$output_dir/license-audit.json" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding='utf-8'))
assert r['status'] == 'review-required'
assert any(i['license'].startswith('GPL') for i in r['reviewRequired'])
PY

  if "$ELF_AUDIT_TOOL" --input "$temp_dir/missing.so" --output "$output_dir/elf-audit.json"; then
    fail 'ELF 审计必须拒绝不存在的输入'
  fi

  printf 'same artifact\n' > "$temp_dir/first.so"
  cp "$temp_dir/first.so" "$temp_dir/second.so"
  "$REPRODUCIBILITY_TOOL" --first "$temp_dir/first.so" --second "$temp_dir/second.so" --output "$output_dir/reproducibility.json"
  assert_json "$output_dir/reproducibility.json"
  printf 'different artifact\n' > "$temp_dir/second.so"
  if "$REPRODUCIBILITY_TOOL" --first "$temp_dir/first.so" --second "$temp_dir/second.so" --output "$output_dir/reproducibility-failure.json"; then
    fail '可重复构建验证必须拒绝不同哈希'
  fi

  if "$CONTROLLED_BUILD" --source "$source_dir" --output "$output_dir/build" --skip-compile; then
    fail '受控构建必须拒绝缺少 libmpv.so 的来源目录'
  fi
}

main "$@"
