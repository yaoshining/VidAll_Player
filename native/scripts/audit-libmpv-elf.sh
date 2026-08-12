#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：audit-libmpv-elf.sh --input <libmpv.so> --output <文件> [--allow <库名>]... [--require <库名>]... [--forbid <库名>]... [--max-bytes <字节>]' >&2
  exit 2
}

input=''
output=''
allows=()
requires=()
forbids=()
max_bytes=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    --allow) allows+=("$2"); shift 2 ;;
    --require) requires+=("$2"); shift 2 ;;
    --forbid) forbids+=("$2"); shift 2 ;;
    --max-bytes) max_bytes="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$input" ] && [ -n "$output" ] || usage
toolchain_root="${OHOS_NDK:-${OHOS_NDK_HOME:-}}"
if [ -n "$toolchain_root" ] && [ -x "$toolchain_root/llvm/bin/llvm-readelf" ]; then
  readelf_tool="$toolchain_root/llvm/bin/llvm-readelf"
  nm_tool="$toolchain_root/llvm/bin/llvm-nm"
elif [ -n "$toolchain_root" ] && [ -x "$toolchain_root/native/llvm/bin/llvm-readelf" ]; then
  readelf_tool="$toolchain_root/native/llvm/bin/llvm-readelf"
  nm_tool="$toolchain_root/native/llvm/bin/llvm-nm"
else
  readelf_tool="$(command -v llvm-readelf || command -v readelf || true)"
  nm_tool="$(command -v llvm-nm || command -v nm || true)"
fi
[ -n "$readelf_tool" ] && [ -n "$nm_tool" ] || { echo '需要 OHOS NDK llvm-readelf/llvm-nm 执行 ELF 审计。' >&2; exit 1; }
mkdir -p "$(dirname "$output")"

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
needed_file="$temp_dir/needed.txt"
symbols_file="$temp_dir/symbols.txt"
undefined_symbols_file="$temp_dir/undefined-symbols.txt"
machine="$($readelf_tool -h "$input" | sed -n 's/^[[:space:]]*Machine:[[:space:]]*//p' | head -n 1)"
"$readelf_tool" -d "$input" | sed -n 's/.*Shared library: \[\(.*\)\].*/\1/p' > "$needed_file"
"$nm_tool" -D --defined-only "$input" 2>/dev/null | awk '{print $NF}' | sed '/^$/d' | LC_ALL=C sort -u > "$symbols_file"
"$nm_tool" -D --undefined-only "$input" 2>/dev/null | awk '{print $NF}' | sed '/^$/d' | LC_ALL=C sort -u > "$undefined_symbols_file"
file_bytes="$(wc -c < "$input" | tr -d ' ')"
python3 - "$output" "$needed_file" "$symbols_file" "$undefined_symbols_file" "$machine" "$file_bytes" "$max_bytes" "${#allows[@]}" "${#requires[@]}" "${allows[@]-}" "${requires[@]-}" "${forbids[@]-}" <<'PY'
import json
import pathlib
import re
import sys
output, needed_path, symbols_path, undefined_symbols_path, machine, file_bytes, max_bytes, allow_count, require_count, *libraries = sys.argv[1:]
allow_count = int(allow_count)
require_count = int(require_count)
allowed = libraries[:allow_count]
required = libraries[allow_count:allow_count + require_count]
forbidden = libraries[allow_count + require_count:]
needed = pathlib.Path(needed_path).read_text(encoding='utf-8').splitlines()
symbols = pathlib.Path(symbols_path).read_text(encoding='utf-8').splitlines()
undefined_symbols = pathlib.Path(undefined_symbols_path).read_text(encoding='utf-8').splitlines()
unauthorized = sorted(set(needed) - set(allowed))
missing_required = sorted(set(required) - set(needed))
forbidden_needed = sorted(set(needed) & set(forbidden))
embedded_symbols = sorted(symbol for symbol in symbols if re.match(r'^(avcodec_|avformat_|av_demuxer_|ff_[a-z0-9_]*(codec|demuxer|muxer))', symbol))
private_ohcodec_symbols = sorted(symbol for symbol in undefined_symbols if re.match(r'^(av_ohcodec_|AVOHCodec)', symbol))
size_exceeded = int(max_bytes) > 0 and int(file_bytes) > int(max_bytes)
architecture_valid = machine in ('AArch64', 'ARM aarch64')
failed = unauthorized or missing_required or forbidden_needed or embedded_symbols or private_ohcodec_symbols or size_exceeded or not architecture_valid
report = {
    'schemaVersion': 2,
    'status': 'failed' if failed else 'passed',
    'machine': machine,
    'architectureValid': architecture_valid,
    'fileBytes': int(file_bytes),
    'maxBytes': int(max_bytes),
    'sizeExceeded': size_exceeded,
    'neededLibraries': needed,
    'allowedLibraries': allowed,
    'requiredLibraries': required,
    'missingRequiredLibraries': missing_required,
    'forbiddenLibraries': forbidden,
    'unauthorizedLibraries': unauthorized,
    'forbiddenNeededLibraries': forbidden_needed,
    'embeddedFfmpegSymbols': embedded_symbols,
    'undefinedPrivateOhcodecSymbols': private_ohcodec_symbols,
    'exportedDynamicSymbols': symbols,
}
pathlib.Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if failed:
    detail = []
    if unauthorized:
        detail.append('存在不允许的动态依赖：' + ', '.join(unauthorized))
    if missing_required:
        detail.append('缺少必需动态依赖：' + ', '.join(missing_required))
    if forbidden_needed:
        detail.append('存在禁止的动态依赖：' + ', '.join(forbidden_needed))
    if embedded_symbols:
        detail.append('疑似内嵌 FFmpeg 实现符号：' + ', '.join(embedded_symbols[:20]))
    if private_ohcodec_symbols:
        detail.append('存在未解析的私有 OHCodec 符号：' + ', '.join(private_ohcodec_symbols[:20]))
    if size_exceeded:
        detail.append(f'产物体积 {file_bytes} 超过预算 {max_bytes}')
    if not architecture_valid:
        detail.append(f'ELF 架构不是 AArch64：{machine or "未知"}')
    raise SystemExit('；'.join(detail))
PY
