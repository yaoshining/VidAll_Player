#!/usr/bin/env bash
# 仅使用本仓库锁定的源码目录与脚本；不下载或执行外部构建 bundle。
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly LOCK_FILE="$ROOT_DIR/native/config/sources.lock.json"
readonly MANIFEST_TOOL="$ROOT_DIR/native/scripts/generate-libmpv-manifest.sh"
readonly SBOM_TOOL="$ROOT_DIR/native/scripts/generate-sbom.sh"
readonly LICENSE_TOOL="$ROOT_DIR/native/scripts/audit-licenses.sh"
readonly NOTICE_TOOL="$ROOT_DIR/native/scripts/collect-licenses.sh"
readonly ELF_AUDIT_TOOL="$ROOT_DIR/native/scripts/audit-libmpv-elf.sh"

usage() {
  echo '用法：build-libmpv-controlled.sh --source <受控源码目录> --output <目录> [--skip-compile]' >&2
  exit 2
}

source_dir=''
output_dir=''
skip_compile=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --source) source_dir="$2"; shift 2 ;;
    --output) output_dir="$2"; shift 2 ;;
    --skip-compile) skip_compile=true; shift ;;
    *) usage ;;
  esac
done
[ -d "$source_dir" ] && [ -n "$output_dir" ] || usage
[ -f "$LOCK_FILE" ] || { echo "未找到来源锁：$LOCK_FILE" >&2; exit 1; }

# 受控构建调用者必须在隔离环境中先检出 sources.lock.json 内指定的提交。
for component in mpv ffmpeg; do
  [ -d "$source_dir/$component" ] || { echo "受控源码缺少：$component" >&2; exit 1; }
done

libmpv="$source_dir/libmpv.so"
if [ "$skip_compile" = false ]; then
  echo '本仓库尚未提交交叉工具链适配层；请在受控的 SDK 容器中产出 libmpv.so 后使用 --skip-compile 生成审计制品。' >&2
  exit 1
fi
[ -f "$libmpv" ] || { echo "受控来源中缺少已构建的 libmpv.so：$libmpv" >&2; exit 1; }

mkdir -p "$output_dir"
cp "$libmpv" "$output_dir/libmpv.so"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$output_dir/libmpv.so" > "$output_dir/libmpv.so.sha256"
else
  shasum -a 256 "$output_dir/libmpv.so" > "$output_dir/libmpv.so.sha256"
fi
"$MANIFEST_TOOL" --lock "$LOCK_FILE" --source "$source_dir" --output "$output_dir/feature-manifest.json" --abi arm64-v8a --min-sdk 15
"$SBOM_TOOL" --lock "$LOCK_FILE" --format spdx --output "$output_dir/sbom.spdx.json"
"$SBOM_TOOL" --lock "$LOCK_FILE" --format cyclonedx --output "$output_dir/sbom.cdx.json"
"$LICENSE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/license-audit.json"
"$NOTICE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/NOTICE"
"$ELF_AUDIT_TOOL" --input "$output_dir/libmpv.so" --output "$output_dir/elf-audit.json" --allow libc++.so --allow libhilog_ndk.z.so
