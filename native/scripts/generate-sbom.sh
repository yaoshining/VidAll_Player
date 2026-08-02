#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：generate-sbom.sh --lock <sources.lock.json> --format <spdx|cyclonedx> --output <文件>' >&2
  exit 2
}

lock_file=''
format=''
output_file=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --lock) lock_file="$2"; shift 2 ;;
    --format) format="$2"; shift 2 ;;
    --output) output_file="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$lock_file" ] && [ -n "$output_file" ] || usage
case "$format" in spdx|cyclonedx) ;; *) usage ;; esac
mkdir -p "$(dirname "$output_file")"

python3 - "$lock_file" "$format" "$output_file" <<'PY'
import json
import pathlib
import sys

lock_path, format_name, output_path = sys.argv[1:]
lock = json.loads(pathlib.Path(lock_path).read_text(encoding='utf-8'))
sources = lock['sources']
if format_name == 'spdx':
    document = {
        'status': 'passed',
        'spdxVersion': 'SPDX-2.3',
        'dataLicense': 'CC0-1.0',
        'SPDXID': 'SPDXRef-DOCUMENT',
        'name': 'VidAll_Player libmpv source SBOM',
        'documentNamespace': 'https://github.com/yaoshining/VidAll_Player/sbom/libmpv',
        'packages': [{
            'SPDXID': 'SPDXRef-' + name,
            'name': name,
            'downloadLocation': value['repository'],
            'versionInfo': value.get('tag', value.get('commit', 'unknown')),
            'externalRefs': [{'referenceCategory': 'OTHER', 'referenceType': 'git' if value.get('commit') else 'archive', 'referenceLocator': value.get('commit', value.get('archiveSha256'))}],
            'licenseConcluded': value['license'],
            'licenseDeclared': value['license'],
            'copyrightText': 'NOASSERTION',
        } for name, value in sources.items()],
    }
else:
    document = {
        'status': 'passed',
        'bomFormat': 'CycloneDX',
        'specVersion': '1.5',
        'serialNumber': 'urn:uuid:00000000-0000-0000-0000-000000000006',
        'version': 1,
        'metadata': {'component': {'type': 'application', 'name': 'VidAll_Player libmpv'}},
        'components': [{
            'type': 'library', 'name': name, 'version': value.get('tag', value.get('commit', 'unknown')),
            'licenses': [{'license': {'id': value['license']}}],
            'externalReferences': [{'type': 'vcs', 'url': value['repository'] + ('@' + value['commit'] if value.get('commit') else '#sha256=' + value['archiveSha256'])}],
        } for name, value in sources.items()],
    }
pathlib.Path(output_path).write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
