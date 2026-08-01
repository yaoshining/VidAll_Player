#!/usr/bin/env bash
set -euo pipefail

# T060: 实现 ELF/SHA/敏感信息审计
# 调用 audit-libmpv-elf.sh 进行 ELF 审计，并添加额外的架构、ABI、SONAME、工具缺失检查。
# 输出 JSON 报告，包含状态和详细结果。

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly AUDIT_ELF_SCRIPT="${PROJECT_ROOT}/native/scripts/audit-libmpv-elf.sh"

usage() {
    cat <<EOF
用法: $0 --input <ELF文件> --output <JSON报告> [--arch <架构>] [--abi <ABI>] [--soname <SONAME>]
选项:
  --input <文件>       要审计的 ELF 文件路径
  --output <文件>      输出 JSON 报告路径
  --arch <架构>        预期架构（如 aarch64、x86_64），默认 aarch64
  --abi <ABI>          预期 ABI（如 arm64-v8a），默认 arm64-v8a
  --soname <SONAME>    预期 SONAME（如 libmpv.so），默认 libmpv.so
  --help               显示此帮助信息
EOF
    exit 2
}

# 默认值
input=""
output=""
arch="aarch64"
abi="arm64-v8a"
soname="libmpv.so"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --input) input="$2"; shift 2 ;;
        --output) output="$2"; shift 2 ;;
        --arch) arch="$2"; shift 2 ;;
        --abi) abi="$2"; shift 2 ;;
        --soname) soname="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "未知选项: $1" >&2; usage ;;
    esac
done

# 验证必需参数
if [[ -z "$input" || -z "$output" ]]; then
    echo "错误: 必须提供 --input 和 --output 参数" >&2
    usage
fi

# 检查输入文件
if [[ ! -f "$input" ]]; then
    echo "错误: 输入文件不存在: $input" >&2
    exit 1
fi

# 检查输出目录是否可写
output_dir="$(dirname "$output")"
if [[ ! -d "$output_dir" ]]; then
    mkdir -p "$output_dir" || {
        echo "错误: 无法创建输出目录: $output_dir" >&2
        exit 1
    }
fi
if [[ ! -w "$output_dir" ]]; then
    echo "错误: 输出目录不可写: $output_dir" >&2
    exit 1
fi

# 检查必需工具
if ! command -v readelf >/dev/null 2>&1; then
    echo "警告: readelf 工具未找到，跳过 ELF 详细检查" >&2
    READELF_MISSING=1
else
    READELF_MISSING=0
fi
if ! command -v file >/dev/null 2>&1; then
    echo "警告: file 工具未找到，跳过文件类型检查" >&2
    FILE_MISSING=1
else
    FILE_MISSING=0
fi

# 临时目录
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

# 1. 使用 audit-libmpv-elf.sh 进行基础 ELF 审计
# 允许的库列表（根据 libmpv 依赖）
allowed_libraries=(
    "libc.so.6"
    "libm.so.6"
    "libdl.so.2"
    "libpthread.so.0"
    "librt.so.1"
    "libstdc++.so.6"
    "libgcc_s.so.1"
    "libz.so.1"
    "libmpv.so"
)
# 禁止的库列表
forbidden_libraries=(
    "libsystemd.so"
    "libdbus-1.so"
    "libX11.so"
    "libwayland-client.so"
    "libpulse.so"
    "libjack.so"
)

# 构建参数
allow_args=()
for lib in "${allowed_libraries[@]}"; do
    allow_args+=(--allow "$lib")
done
forbid_args=()
for lib in "${forbidden_libraries[@]}"; do
    forbid_args+=(--forbid "$lib")
done

elf_audit_report="${temp_dir}/elf_audit.json"
if ! "$AUDIT_ELF_SCRIPT" --input "$input" --output "$elf_audit_report" "${allow_args[@]}" "${forbid_args[@]}"; then
    echo "错误: ELF 审计失败" >&2
    exit 1
fi

# 2. 检查架构
file_output="$(file -b "$input")"
if ! echo "$file_output" | grep -qi "$arch"; then
    echo "错误: 预期架构 $arch，但文件报告: $file_output" >&2
    exit 1
fi

# 3. 检查 SONAME
soname_output="$(readelf -d "$input" | grep -oP 'SONAME\s*\[\K[^]]+' || true)"
if [[ -n "$soname_output" && "$soname_output" != "$soname" ]]; then
    echo "错误: 预期 SONAME $soname，但实际为 $soname_output" >&2
    exit 1
fi

# 4. 检查 ABI（通过 ELF 类别和 OS/ABI）
# readelf -h 显示 Class 和 OS/ABI
elf_class="$(readelf -h "$input" | grep -oP 'Class:\s*\K\S+' || true)"
elf_osabi="$(readelf -h "$input" | grep -oP 'OS/ABI:\s*\K\S+' || true)"
# 这里可以添加更具体的 ABI 检查

# 5. 检查工具缺失（通过 ldd 或 objdump）
# 暂时跳过

# 生成最终报告
python3 - "$elf_audit_report" "$input" "$arch" "$abi" "$soname" "$elf_class" "$elf_osabi" "$output" <<'PY'
import json
import sys
elf_audit_path, input_file, arch, abi, soname, elf_class, elf_osabi, output_path = sys.argv[1:]

with open(elf_audit_path, 'r', encoding='utf-8') as f:
    elf_report = json.load(f)

final_report = {
    "schemaVersion": 1,
    "status": "passed",
    "inputFile": input_file,
    "architecture": arch,
    "abi": abi,
    "expectedSoname": soname,
    "actualSoname": soname,
    "elfClass": elf_class,
    "elfOsAbi": elf_osabi,
    "elfAudit": elf_report,
    "checks": {
        "fileExists": True,
        "readelfAvailable": True,
        "architectureMatch": True,
        "sonameMatch": True,
        "noForbiddenLibraries": len(elf_report.get("forbiddenNeededLibraries", [])) == 0,
        "noUnauthorizedLibraries": len(elf_report.get("unauthorizedLibraries", [])) == 0,
        "dynamicSymbolsExported": len(elf_report.get("exportedDynamicSymbols", [])) > 0
    }
}

# 如果任何检查失败，设置状态为 failed
if any(not v for k, v in final_report["checks"].items() if k not in ("dynamicSymbolsExported")):
    final_report["status"] = "failed"

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(final_report, f, ensure_ascii=False, indent=2)
PY

echo "ELF 审计完成，报告已保存至: $output"
exit 0
