#!/usr/bin/env bash
set -euo pipefail

# T060: 敏感信息扫描
# 扫描指定目录中的敏感信息（密钥、密码、令牌等）并生成报告。

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<EOF
用法: $0 --directory <目录> --output <JSON报告> [--exclude <模式>...]
选项:
  --directory <目录>   要扫描的目录路径
  --output <文件>      输出 JSON 报告路径
  --exclude <模式>     排除的文件/目录模式（可多次使用）
  --help               显示此帮助信息
EOF
    exit 2
}

# 解析参数
directory=""
output=""
exclude_patterns=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --directory) directory="$2"; shift 2 ;;
        --output) output="$2"; shift 2 ;;
        --exclude) exclude_patterns+=("$2"); shift 2 ;;
        --help) usage ;;
        *) echo "未知选项: $1" >&2; usage ;;
    esac
done

# 验证必需参数
if [[ -z "$directory" || -z "$output" ]]; then
    echo "错误: 必须提供 --directory 和 --output 参数" >&2
    usage
fi

if [[ ! -d "$directory" ]]; then
    echo "错误: 目录不存在: $directory" >&2
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
command -v grep >/dev/null 2>&1 || {
    echo "错误: 需要 grep 工具" >&2
    exit 1
}

# 临时文件
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
result_file="${temp_dir}/results.json"
findings_file="${temp_dir}/findings.jsonl"

# 敏感数据模式（简单正则表达式）
patterns=(
    'password\s*[:=]\s*["'\''`]?[^"\'\''`\s]{6,}["'\''`]?'
    'secret\s*[:=]\s*["'\''`]?[^"\'\''`\s]{6,}["'\''`]?'
    'api[_-]?key\s*[:=]\s*["'\''`]?[^"\'\''`\s]{10,}["'\''`]?'
    'token\s*[:=]\s*["'\''`]?[^"\'\''`\s]{10,}["'\''`]?'
    '-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----'
    'AKIA[0-9A-Z]{16}'
    '-----BEGIN OPENSSH PRIVATE KEY-----'
)

# 构建 find 命令
find_cmd=(find "$directory" -type f)
for pattern in "${exclude_patterns[@]:-}"; do
    find_cmd+=(-not -path "$pattern")
done

# 扫描结果
total_files=0
files_with_sensitive=0
# 将发现写入 JSONL 临时文件，避免 shell 变量拼接 JSON 的问题
: > "$findings_file"

# 扫描文件
while IFS= read -r file; do
    ((total_files++)) || true
    # 跳过二进制文件
    if file "$file" 2>/dev/null | grep -q 'binary'; then
        continue
    fi
    file_sensitive=false
    for pattern in "${patterns[@]}"; do
        if grep -q -E "$pattern" "$file" 2>/dev/null; then
            file_sensitive=true
            # 将匹配写入临时文件，由 Python 安全地构建 JSON
            echo "$file" >> "$findings_file"
        fi
    done
    if [[ "$file_sensitive" == true ]]; then
        ((files_with_sensitive++)) || true
    fi
done < <("${find_cmd[@]}" 2>/dev/null | head -1000)  # 限制文件数量

# 生成 JSON 报告（Python 安全处理所有数据）
python3 - "$directory" "$output" "$total_files" "$files_with_sensitive" "$findings_file" <<'PY'
import json
import sys

directory = sys.argv[1]
output_path = sys.argv[2]
total_files = int(sys.argv[3])
files_with_sensitive = int(sys.argv[4])
findings_path = sys.argv[5]

# 从临时文件读取发现记录
sensitive_data_found = []
pattern_counts = {}
try:
    with open(findings_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                entry = {"file": line, "pattern": "detected"}
                sensitive_data_found.append(entry)
                pattern_counts["detected"] = pattern_counts.get("detected", 0) + 1
except FileNotFoundError:
    pass

report = {
    "schemaVersion": 1,
    "status": "passed" if files_with_sensitive == 0 else "failed",
    "scannedDirectory": directory,
    "excludedPatterns": [],
    "summary": {
        "totalFilesScanned": total_files,
        "filesWithSensitiveData": files_with_sensitive,
        "patternsDetected": pattern_counts
    },
    "sensitiveDataFound": sensitive_data_found
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
PY

echo "敏感信息扫描完成，报告已保存至: $output"
if [[ $files_with_sensitive -gt 0 ]]; then
    echo "发现 $files_with_sensitive 个文件包含敏感信息"
    exit 1
else
    exit 0
fi