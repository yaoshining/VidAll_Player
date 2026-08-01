#!/usr/bin/env bash
set -euo pipefail
usage() { echo '用法: scan-sensitive-data.sh --directory <目录> --output <JSON报告> [--exclude <模式>...]' >&2; exit 2; }
directory='' output=''; excludes=()
while [ "$#" -gt 0 ]; do
  case "$1" in --directory) directory="$2"; shift 2;; --output) output="$2"; shift 2;; --exclude) excludes+=("$2"); shift 2;; --help) usage;; *) usage;; esac
done
[ -d "$directory" ] && [ -n "$output" ] || usage
mkdir -p "$(dirname "$output")"
args=("$directory" "$output")
if [ "${#excludes[@]}" -gt 0 ]; then
  args+=("${excludes[@]}")
fi
python3 - "${args[@]}" <<'PY'
import fnmatch, json, pathlib, re, sys
root, output, *excludes = sys.argv[1:]
patterns = [
 ('password', re.compile(r'''password[\s]*[:=][\s]*["'`]?[^"'`\s]{6,}["'`]?''', re.I)),
 ('secret', re.compile(r'''secret[\s]*[:=][\s]*["'`]?[^"'`\s]{6,}["'`]?''', re.I)),
 ('api-key', re.compile(r'''api[_-]?key[\s]*[:=][\s]*["'`]?[^"'`\s]{10,}["'`]?''', re.I)),
 ('token', re.compile(r'''token[\s]*[:=][\s]*["'`]?[^"'`\s]{10,}["'`]?''', re.I)),
 ('private-key', re.compile(r'-----BEGIN (?:(?:RSA|DSA|EC|OPENSSH) )?(?:ENCRYPTED )?PRIVATE KEY-----')),
 ('aws-key', re.compile(r'AKIA[0-9A-Z]{16}')),
]
findings=[]; total=0
for path in pathlib.Path(root).rglob('*'):
    if not path.is_file() or any(fnmatch.fnmatch(str(path), item) for item in excludes): continue
    total += 1
    try: data=path.read_bytes()
    except OSError: continue
    if b'\0' in data: continue
    text=data.decode('utf-8', errors='replace')
    names=[name for name, regex in patterns if regex.search(text)]
    if names: findings.append({'file': str(path), 'patterns': names})
report={'schemaVersion':1,'status':'failed' if findings else 'passed','scannedDirectory':root,'excludedPatterns':excludes,'summary':{'totalFilesScanned':total,'filesWithSensitiveData':len(findings),'truncated':False},'sensitiveDataFound':findings}
pathlib.Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sys.exit(1 if findings else 0)
PY
