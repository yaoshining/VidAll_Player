#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：audit-libmpv-elf.sh --input <libmpv.so> --output <文件> [--allow <库名>]...' >&2
  exit 2
}

input=''
output=''
allows=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    --allow) allows+=("$2"); shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$input" ] && [ -n "$output" ] || usage
command -v readelf >/dev/null 2>&1 || { echo '需要 readelf 执行 ELF 审计。' >&2; exit 1; }
mkdir -p "$(dirname "$output")"

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
needed_file="$temp_dir/needed.txt"
symbols_file="$temp_dir/symbols.txt"
readelf -d "$input" | sed -n 's/.*Shared library: \[\(.*\)\].*/\1/p' > "$needed_file"
readelf --dyn-syms --wide "$input" | awk 'NR > 3 {print $8}' | sed '/^$/d' | LC_ALL=C sort -u > "$symbols_file"
python3 - "$output" "$needed_file" "$symbols_file" "${allows[@]}" <<'PY'
import json
import pathlib
import sys
output, needed_path, symbols_path, *allowed = sys.argv[1:]
needed = pathlib.Path(needed_path).read_text(encoding='utf-8').splitlines()
symbols = pathlib.Path(symbols_path).read_text(encoding='utf-8').splitlines()
unauthorized = sorted(set(needed) - set(allowed))
report = {
    'schemaVersion': 1,
    'status': 'passed' if not unauthorized else 'failed',
    'neededLibraries': needed,
    'allowedLibraries': allowed,
    'unauthorizedLibraries': unauthorized,
    'exportedDynamicSymbols': symbols,
}
pathlib.Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if unauthorized:
    raise SystemExit('存在不允许的动态依赖：' + ', '.join(unauthorized))
PY
