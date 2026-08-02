#!/usr/bin/env bash
set -euo pipefail

# T062: 生成供 create-candidate.sh 消费的验证构件。
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly SBOM_SCRIPT="${VERIFICATION_SBOM_SCRIPT:-${PROJECT_ROOT}/native/scripts/generate-sbom.sh}"
readonly LICENSES_SCRIPT="${VERIFICATION_LICENSES_SCRIPT:-${PROJECT_ROOT}/native/scripts/generate-licenses.sh}"
readonly VERIFY_RELEASE_SCRIPT="${VERIFICATION_ELF_AUDIT_SCRIPT:-${PROJECT_ROOT}/scripts/audit/verify-release.sh}"

usage() {
  cat >&2 <<EOF_USAGE
用法: $0 --lock <sources.lock.json> --elf <libmpv.so> --output <manifest.json> [选项]
  --sbom-format <spdx|cyclonedx>  SBOM 格式（默认 spdx）
  --notice <NOTICE.txt>            NOTICE 输出路径
  --internal-load <json>           已通过的 HAR 内部装入证明
  --consumer-smoke <json>          已通过的 consumer-smoke 证明
  --arch <架构> --abi <ABI>         ELF 预期架构与 ABI（默认 aarch64 / arm64-v8a）
EOF_USAGE
  exit 2
}

lock_file='' elf_file='' output_file='' sbom_format='spdx' notice_file=''
internal_load_file='' consumer_smoke_file='' arch='aarch64' abi='arm64-v8a'
while [ "$#" -gt 0 ]; do
  case "$1" in
    --lock|--elf|--output|--sbom-format|--notice|--internal-load|--consumer-smoke|--arch|--abi)
      [ "$#" -ge 2 ] || usage
      case "$1" in
        --lock) lock_file="$2" ;; --elf) elf_file="$2" ;; --output) output_file="$2" ;;
        --sbom-format) sbom_format="$2" ;; --notice) notice_file="$2" ;;
        --internal-load) internal_load_file="$2" ;; --consumer-smoke) consumer_smoke_file="$2" ;;
        --arch) arch="$2" ;; --abi) abi="$2" ;;
      esac
      shift 2 ;;
    --help) usage ;;
    *) echo "未知选项: $1" >&2; usage ;;
  esac
done
[ -f "$lock_file" ] && [ -f "$elf_file" ] && [ -n "$output_file" ] || { echo '错误: 必须提供存在的 --lock、--elf 和 --output。' >&2; exit 1; }
[ -x "$SBOM_SCRIPT" ] && [ -x "$LICENSES_SCRIPT" ] && [ -x "$VERIFY_RELEASE_SCRIPT" ] || { echo '错误: 验证工具不可执行。' >&2; exit 1; }

temp_dir="$(mktemp -d)"; trap 'rm -rf "$temp_dir"' EXIT
sbom_file="$temp_dir/sbom.json"; licenses_file="$temp_dir/licenses.json"; elf_audit_file="$temp_dir/elf-audit.json"
"$SBOM_SCRIPT" --lock "$lock_file" --format "$sbom_format" --output "$sbom_file"
license_args=(--lock "$lock_file" --output "$licenses_file")
[ -z "$notice_file" ] || license_args+=(--notice "$notice_file")
"$LICENSES_SCRIPT" "${license_args[@]}"
"$VERIFY_RELEASE_SCRIPT" --input "$elf_file" --output "$elf_audit_file" --arch "$arch" --abi "$abi" --soname libmpv.so

if [ -z "$internal_load_file" ]; then internal_load_file="$PROJECT_ROOT/release/audits/har-native-packaging-spike.json"; fi
if [ -z "$consumer_smoke_file" ]; then consumer_smoke_file="$PROJECT_ROOT/release/audits/consumer-smoke.json"; fi
[ -f "$internal_load_file" ] || { echo "错误: 内部装入证明不存在: $internal_load_file" >&2; exit 1; }
[ -f "$consumer_smoke_file" ] || { echo "错误: consumer-smoke 证明不存在: $consumer_smoke_file" >&2; exit 1; }

python3 - "$lock_file" "$elf_file" "$sbom_file" "$licenses_file" "$elf_audit_file" "$internal_load_file" "$consumer_smoke_file" "$output_file" <<'PY'
import datetime, hashlib, json, pathlib, sys
lock_path, elf_path, sbom_path, licenses_path, audit_path, har_path, smoke_path, output_path = sys.argv[1:]
def read(path): return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
def passed(document, key='status'):
    return document.get(key) in ('passed', 'verified', 'compliant')
lock, sbom, licenses, audit, har, smoke = map(read, (lock_path, sbom_path, licenses_path, audit_path, har_path, smoke_path))
version = lock.get('releaseVersion') or lock.get('sources', {}).get('mpv', {}).get('tag')
if not version:
    raise SystemExit('错误: 锁文件缺少 releaseVersion 或 mpv tag，无法生成候选版本。')
evidence = {
  'sbom': {'valid': passed(sbom), 'summary': f"SBOM: {sbom.get('status', 'missing')}"},
  'licenses': {'valid': licenses.get('complianceStatus') == 'compliant', 'summary': f"许可证结论: {licenses.get('complianceStatus', 'missing')}"},
  'elfAudit': {'valid': passed(audit), 'summary': f"ELF 审计: {audit.get('status', 'missing')}"},
  'harInclusion': {'valid': passed(har), 'summary': f"HAR 内部装入证明: {har.get('status', 'missing')}"},
  'consumerSmoke': {'valid': passed(smoke), 'summary': f"consumer-smoke 证明: {smoke.get('status', 'missing')}"},
}
valid = all(item['valid'] for item in evidence.values())
manifest = {
  'schemaVersion': 1, 'artifactType': 'verification', 'version': version,
  'sha256': hashlib.sha256(pathlib.Path(elf_path).read_bytes()).hexdigest(),
  'status': 'verified' if valid else 'failed', 'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'lockFile': lock_path, 'elfFile': elf_path, 'evidence': evidence,
}
pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(output_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if not valid: raise SystemExit('错误: 验证证据未全部通过，已生成 failed manifest。')
PY

echo "验证构件 manifest 已生成: $output_file"
