#!/usr/bin/env bash
set -euo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly VERIFY_SCRIPT="${PROJECT_ROOT}/scripts/audit/verify-release.sh"
readonly TEST_DIR="${PROJECT_ROOT}/.test-audit-verify-release"
cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT
failures=0
assert_fails() { if "$@" >/dev/null 2>&1; then echo "✗ 应当失败: $*" >&2; return 1; fi; }
setup_tools() {
  local needed="$1" elf_class="${2:-ELF64}" elf_osabi="${3:-UNIX - System V}" tools="$TEST_DIR/tools"
  rm -rf "$tools"
  mkdir -p "$tools"
  for tool in env bash dirname mkdir mktemp rm sed awk sort grep python3 cat; do
    ln -s "$(command -v "$tool")" "$tools/$tool"
  done
  cat > "$tools/file" <<'SH'
#!/usr/bin/env bash
echo 'ELF 64-bit LSB shared object, ARM aarch64'
SH
  cat > "$tools/readelf" <<SH
#!/usr/bin/env bash
case "\$1" in
  -d) cat <<'OUT'
 0x000000000000000e (SONAME)             Library soname: [libmpv.so]
 0x0000000000000001 (NEEDED)             Shared library: [$needed]
OUT
  ;;
  -h) printf '  Class:                             %s\n  OS/ABI:                            %s\n' '$elf_class' '$elf_osabi' ;;
  --dyn-syms) printf 'Symbol table\nfoo\nbar\nexample_symbol\n' ;;
esac
SH
  chmod +x "$tools/file" "$tools/readelf"
}
run_with_tools() { PATH="$TEST_DIR/tools" "$VERIFY_SCRIPT" "$@"; }
main() {
  cleanup; mkdir -p "$TEST_DIR"
  : > "$TEST_DIR/input.so"
  echo '=== 测试 1: 缺少输入文件 ==='
  assert_fails "$VERIFY_SCRIPT" --input "$TEST_DIR/missing.so" --output "$TEST_DIR/out.json" || ((failures++))
  echo '=== 测试 2: 缺少 readelf 工具 ==='
  mkdir -p "$TEST_DIR/no-readelf"; for tool in env bash dirname mkdir mktemp rm; do ln -s "$(command -v "$tool")" "$TEST_DIR/no-readelf/$tool"; done
  if output="$(PATH="$TEST_DIR/no-readelf" "$VERIFY_SCRIPT" --input "$TEST_DIR/input.so" --output "$TEST_DIR/out.json" 2>&1)" && false; then :; elif printf '%s\n' "$output" | grep -q '需要 readelf'; then :; else echo "✗ 未拒绝缺少 readelf: $output" >&2; ((failures++)); fi
  echo '=== 测试 3: 禁止依赖库 ==='
  setup_tools libX11.so
  assert_fails run_with_tools --input "$TEST_DIR/input.so" --output "$TEST_DIR/forbidden.json" || ((failures++))
  echo '=== 测试 4: 正常路径 ==='
  setup_tools libc.so.6
  run_with_tools --input "$TEST_DIR/input.so" --output "$TEST_DIR/passed.json" || ((failures++))
  python3 - "$TEST_DIR/passed.json" <<'PY' || ((failures++))
import json, sys
report=json.load(open(sys.argv[1], encoding='utf-8'))
assert report['status'] == 'passed'
assert report['actualSoname'] == 'libmpv.so'
PY
  echo '=== 测试 5: ABI 类别不匹配必须失败 ==='
  setup_tools libc.so.6 ELF32
  assert_fails run_with_tools --input "$TEST_DIR/input.so" --output "$TEST_DIR/abi-mismatch.json" || ((failures++))
  [ "$failures" -eq 0 ] || { echo "有 $failures 个测试失败" >&2; exit 1; }
  echo '所有 ELF 审计测试通过'
}
main "$@"
