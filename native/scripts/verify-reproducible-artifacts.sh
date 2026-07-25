#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：verify-reproducible-artifacts.sh --first <制品> --second <制品> --output <报告>' >&2
  exit 2
}

first=''
second=''
output=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --first) first="$2"; shift 2 ;;
    --second) second="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$first" ] && [ -f "$second" ] && [ -n "$output" ] || usage
mkdir -p "$(dirname "$output")"

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi
}
first_hash="$(hash_file "$first")"
second_hash="$(hash_file "$second")"
python3 - "$output" "$first_hash" "$second_hash" <<'PY'
import json
import pathlib
import sys
first, second = sys.argv[2:]
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    'schemaVersion': 1,
    'firstSha256': first,
    'secondSha256': second,
    'reproducible': first == second,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
[ "$first_hash" = "$second_hash" ] || { echo '制品 SHA-256 不一致，构建不可重复。' >&2; exit 1; }
