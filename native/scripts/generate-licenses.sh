#!/usr/bin/env bash
set -euo pipefail

usage() { echo '用法：generate-licenses.sh --lock <sources.lock.json> --output <文件> [--notice <NOTICE文件>]' >&2; exit 2; }
lock_file='' output_file='' notice_file=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --lock) lock_file="$2"; shift 2 ;;
    --output) output_file="$2"; shift 2 ;;
    --notice) notice_file="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$lock_file" ] && [ -n "$output_file" ] || usage
mkdir -p "$(dirname "$output_file")"
[ -z "$notice_file" ] || mkdir -p "$(dirname "$notice_file")"

python3 - "$lock_file" "$output_file" "$notice_file" <<'PY'
import json
import pathlib
import sys

lock_path, output_path, notice_path = sys.argv[1:]
lock = json.loads(pathlib.Path(lock_path).read_text(encoding='utf-8'))
sources = lock.get('sources', {})
policy = lock.get('licensePolicy', {})
licenses = {}
for name, info in sources.items():
    license_id = info.get('license', 'UNKNOWN')
    licenses.setdefault(license_id, []).append(name)
unknown = sorted(licenses.get('UNKNOWN', []))
review_licenses = set(policy.get('releaseRequiresReview', []))
review_components = sorted(component for license_id, components in licenses.items()
                           if license_id in review_licenses for component in components)
status = 'non-compliant' if unknown else ('requires-review' if review_components else 'compliant')
conclusion = {
    'schemaVersion': 1,
    'generatedFrom': lock_path,
    'licenseSummary': [{'license': license_id, 'components': sorted(components)}
                       for license_id, components in sorted(licenses.items())],
    'unknownLicenseComponents': unknown,
    'licensesRequiringReview': review_components,
    'noticeRequired': policy.get('noticeRequired') is True,
    'sourceOfferRequired': policy.get('sourceOfferRequired') is True,
    'complianceStatus': status,
}
pathlib.Path(output_path).write_text(json.dumps(conclusion, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if notice_path:
    lines = ['NOTICE', '======', '', '本产品包含以下第三方组件：', '']
    for license_id, components in sorted(licenses.items()):
        lines.append(f'许可证: {license_id}')
        for component in sorted(components):
            info = sources[component]
            lines.append(f"  - {component} {info.get('tag', 'N/A')} ({info.get('commit', 'N/A')})")
            lines.append(f"    来源: {info.get('repository', 'N/A')}")
            lines.append('    版权声明与完整许可证正文：请参见该组件上游发行包中的 LICENSE/COPYING 文件。')
        lines.append('')
    if policy.get('sourceOfferRequired') is True:
        lines.extend(['源码获取：可按上述仓库和不可变 commit 获取对应源码；发布方应按适用许可证提供完整对应源码。', ''])
    pathlib.Path(notice_path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY

echo "许可证结论已生成: $output_file"
[ -z "$notice_file" ] || echo "NOTICE 文件已生成: $notice_file"
