#!/usr/bin/env bash
set -euo pipefail
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SCANNER="$ROOT/scripts/audit/scan-sensitive-data.sh"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
mkdir -p "$temp_dir/files"
printf 'token=abcdefghijk\n' > "$temp_dir/files/secret.txt"
printf 'password=abcdef\n' > "$temp_dir/files/another.txt"
printf '%s\n' '-----BEGIN PRIVATE KEY-----' > "$temp_dir/files/pkcs8.pem"
printf '%s\n' '-----BEGIN ENCRYPTED PRIVATE KEY-----' > "$temp_dir/files/encrypted-pkcs8.pem"
printf '\0token=abcdefghijk' > "$temp_dir/files/binary.bin"
for number in $(seq 1 1001); do printf 'safe\n' > "$temp_dir/files/safe-$number.txt"; done
if "$SCANNER" --directory "$temp_dir/files" --output "$temp_dir/report.json"; then
  echo '应当发现敏感信息' >&2; exit 1
fi
python3 - "$temp_dir/report.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
assert report['status'] == 'failed'
assert report['summary']['totalFilesScanned'] == 1006
assert report['summary']['filesWithSensitiveData'] == 4
assert report['summary']['truncated'] is False
assert len(report['sensitiveDataFound']) == 4
assert any('pkcs8.pem' in item['file'] and 'private-key' in item['patterns'] for item in report['sensitiveDataFound'])
assert any('encrypted-pkcs8.pem' in item['file'] and 'private-key' in item['patterns'] for item in report['sensitiveDataFound'])
assert all('binary.bin' not in item['file'] for item in report['sensitiveDataFound'])
PY
