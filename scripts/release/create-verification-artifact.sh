#!/usr/bin/env bash
set -euo pipefail

# T062: 创建验证构件 manifest
# 整合 SBOM、许可证结论、ELF 审计、内部装入证明、consumer-smoke 证明等。

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly SBOM_SCRIPT="${PROJECT_ROOT}/native/scripts/generate-sbom.sh"
readonly LICENSES_SCRIPT="${PROJECT_ROOT}/native/scripts/generate-licenses.sh"
readonly AUDIT_ELF_SCRIPT="${PROJECT_ROOT}/native/scripts/audit-libmpv-elf.sh"
readonly VERIFY_RELEASE_SCRIPT="${PROJECT_ROOT}/scripts/audit/verify-release.sh"

usage() {
    cat <<EOF
用法: $0 --lock <sources.lock.json> --elf <libmpv.so> --output <manifest.json> [--sbom-format <spdx|cyclonedx>] [--notice <NOTICE.txt>]
选项:
  --lock <文件>          sources.lock.json 路径
  --elf <文件>           要审计的 ELF 文件路径
  --output <文件>        输出 manifest 文件路径
  --sbom-format <格式>   SBOM 格式 (spdx 或 cyclonedx，默认 spdx)
  --notice <文件>        可选的 NOTICE 文件输出路径
  --help                 显示此帮助信息
EOF
    exit 2
}

lock_file=''
elf_file=''
output_file=''
sbom_format='spdx'
notice_file=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        --lock) lock_file="$2"; shift 2 ;;
        --elf) elf_file="$2"; shift 2 ;;
        --output) output_file="$2"; shift 2 ;;
        --sbom-format) sbom_format="$2"; shift 2 ;;
        --notice) notice_file="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "未知选项: $1" >&2; usage ;;
    esac
done

# 验证必需参数
if [[ -z "$lock_file" || -z "$elf_file" || -z "$output_file" ]]; then
    echo "错误: 必须提供 --lock、--elf 和 --output 参数" >&2
    usage
fi

if [[ ! -f "$lock_file" ]]; then
    echo "错误: 锁文件不存在: $lock_file" >&2
    exit 1
fi
if [[ ! -f "$elf_file" ]]; then
    echo "错误: ELF 文件不存在: $elf_file" >&2
    exit 1
fi

# 检查必需脚本
for script in "$SBOM_SCRIPT" "$LICENSES_SCRIPT" "$AUDIT_ELF_SCRIPT" "$VERIFY_RELEASE_SCRIPT"; do
    if [[ ! -x "$script" ]]; then
        echo "错误: 必需脚本不存在或不可执行: $script" >&2
        exit 1
    fi
done

# 临时目录
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

# 生成 SBOM
sbom_file="${temp_dir}/sbom.json"
"$SBOM_SCRIPT" --lock "$lock_file" --format "$sbom_format" --output "$sbom_file"

# 生成许可证结论
licenses_file="${temp_dir}/licenses.json"
if [[ -n "$notice_file" ]]; then
    "$LICENSES_SCRIPT" --lock "$lock_file" --output "$licenses_file" --notice "$notice_file"
else
    "$LICENSES_SCRIPT" --lock "$lock_file" --output "$licenses_file"
fi

# 执行 ELF 审计
elf_audit_file="${temp_dir}/elf_audit.json"
"$VERIFY_RELEASE_SCRIPT" --input "$elf_file" --output "$elf_audit_file" --arch aarch64 --abi arm64-v8a --soname libmpv.so

# 收集其他证据（占位符）
internal_load_file="${temp_dir}/internal_load.json"
if [[ -f "${PROJECT_ROOT}/release/audits/har-native-packaging-spike.json" ]]; then
    cp "${PROJECT_ROOT}/release/audits/har-native-packaging-spike.json" "$internal_load_file"
else
    echo '{"status": "missing", "message": "内部装入证明未找到"}' > "$internal_load_file"
fi

consumer_smoke_file="${temp_dir}/consumer_smoke.json"
if [[ -f "${PROJECT_ROOT}/release/audits/consumer-smoke.json" ]]; then
    cp "${PROJECT_ROOT}/release/audits/consumer-smoke.json" "$consumer_smoke_file"
else
    echo '{"status": "missing", "message": "consumer-smoke 证明未找到"}' > "$consumer_smoke_file"
fi

# 生成最终 manifest
python3 - "$lock_file" "$elf_file" "$sbom_file" "$licenses_file" "$elf_audit_file" "$internal_load_file" "$consumer_smoke_file" "$output_file" <<'PY'
import json
import pathlib
import sys
import datetime

lock_path, elf_path, sbom_path, licenses_path, elf_audit_path, internal_load_path, consumer_smoke_path, output_path = sys.argv[1:]

def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

manifest = {
    "schemaVersion": 1,
    "type": "verification-artifact",
    "lockFile": lock_path,
    "elfFile": elf_path,
    "sbom": read_json(sbom_path),
    "licenseConclusion": read_json(licenses_path),
    "elfAudit": read_json(elf_audit_path),
    "internalLoadProof": read_json(internal_load_path),
    "consumerSmokeProof": read_json(consumer_smoke_path),
    "status": "candidate",
    "timestamp": datetime.datetime.fromtimestamp(
        pathlib.Path(lock_path).stat().st_mtime,
        tz=datetime.timezone.utc
    ).isoformat()
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
PY

echo "验证构件 manifest 已生成: $output_file"
exit 0
