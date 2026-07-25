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

needed="$(readelf -d "$input" | sed -n 's/.*Shared library: \[\(.*\)\].*/\1/p')"
symbols="$(readelf --dyn-syms --wide "$input" | awk 'NR > 3 {print $8}' | sed '/^$/d' | sort -u)"
python3 - "$output" "$needed" "$symbols" "${allows[@]}" <<'PY'
import json
import pathlib
import sys
output, needed_text, symbols_text, *allowed = sys.argv[1:]
needed = [line for line in needed_text.splitlines() if line]
symbols = [line for line in symbols_text.splitlines() if line]
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
