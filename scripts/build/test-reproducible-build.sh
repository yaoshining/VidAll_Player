#!/usr/bin/env bash
# T057：受控离线构建失败测试。
# 未校验下载、bootstrap 脚本、缺缓存输入均必须失败。
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly BUILD_SCRIPT="$PROJECT_ROOT/native/scripts/build-libmpv-controlled.sh"
readonly LOCK_FILE="$PROJECT_ROOT/native/config/sources.lock.json"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

[ -f "$BUILD_SCRIPT" ] || fail "构建脚本不存在：$BUILD_SCRIPT"
[ -f "$LOCK_FILE" ] || fail "来源锁不存在：$LOCK_FILE"

# 临时目录全局清理列表
TEMP_DIRS_TO_CLEAN=()
cleanup_temp_dirs() {
  [ "${#TEMP_DIRS_TO_CLEAN[@]}" -gt 0 ] && rm -rf "${TEMP_DIRS_TO_CLEAN[@]}" 2>/dev/null || true
}
trap cleanup_temp_dirs EXIT

# 辅助函数：创建临时目录并注册清理
setup_temp() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  TEMP_DIRS_TO_CLEAN+=("$temp_dir")
  echo "$temp_dir"
}

# 辅助函数：创建最小化有效来源锁
create_minimal_lock() {
  python3 - "$1" <<'PY'
import json
import sys
lock = {
    "schemaVersion": 3,
    "sources": {
        "mpv": {
            "repository": "https://example.invalid/mpv.git",
            "tag": "v0.40.0",
            "commit": "287d7cdb78975ae350d7c2a287eae3c2072c93f7",
            "license": "GPL-2.0-or-later",
            "purpose": "libmpv 核心",
            "fetchMethod": "archive",
            "archiveSha256": "1" * 64
        },
        "ffmpeg": {
            "repository": "https://example.invalid/ffmpeg.git",
            "tag": "n7.1.1",
            "commit": "a1328e68877e12ab5a6e5d92a84aefa566783ea5",
            "license": "LGPL-2.1-or-later",
            "purpose": "解封装",
            "fetchMethod": "archive",
            "archiveSha256": "2" * 64
        },
        "samba": {
            "repository": "https://example.invalid/samba.git",
            "tag": "samba-4.20.7",
            "commit": "3984b04d7085c428ab3126ef4cfac2a396b5b29e",
            "license": "GPL-3.0-or-later",
            "purpose": "libsmbclient",
            "fetchMethod": "archive",
            "archiveSha256": "3" * 64,
            "build": {
                "target": "aarch64-linux-ohos",
                "pkgConfigModule": "smbclient",
                "linkage": "static",
                "dependencyClosureStatus": "complete",
                "transitiveDependencies": ["zlib", "popt", "gnutls"]
            }
        },
        "gnutls": {
            "repository": "https://example.invalid/gnutls.git",
            "tag": "3.8.7",
            "commit": "994d9392a607308e452ecae87caafd6ea81288f3",
            "license": "LGPL-2.1-or-later",
            "purpose": "TLS",
            "fetchMethod": "git-checkout"
        },
        "popt": {
            "repository": "https://example.invalid/popt.git",
            "tag": "popt-1.19-release",
            "commit": "916e61045d268f7e37ade5ec047eb77e8299e6ad",
            "license": "MIT",
            "purpose": "命令行",
            "fetchMethod": "git-checkout"
        },
        "zlib": {
            "repository": "https://example.invalid/zlib.git",
            "tag": "v1.3.1",
            "commit": "925af44f3cde53c6b076611c297850091b5dc7bb",
            "license": "Zlib",
            "purpose": "压缩",
            "fetchMethod": "git-checkout"
        }
    },
    "submodules": {"mpv": [], "ffmpeg": []},
    "patches": [{"path": "native/patches/libmpv-ohos-build/0001.patch", "sha256": "a" * 64, "appliesTo": "mpv"}],
    "tools": {
        "meson": {"version": "1.7.0", "sha256": "ae3f12953045f3c7c60e27f2af1ad862f14dee125b4ed9bcb8a842a5080dbf85"},
        "ninja": {"version": "1.11.1", "digests": {"macosx-arm64": "b" * 64, "manylinux-x86_64": "c" * 64}},
        "python": {"version": "3.10", "sha256": "0" * 64}
    },
    "buildSwitches": {"targetAbi": "aarch64-linux-ohos", "linkage": "static", "gpl": True},
    "licensePolicy": {
        "releaseRequiresReview": ["GPL-2.0-or-later", "GPL-3.0-or-later", "LGPL-2.1-or-later"],
        "noticeRequired": True,
        "sourceOfferRequired": True
    }
}
with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump(lock, handle, ensure_ascii=False, indent=2)
PY
}

# 创建 mock 项目根目录，包含构建脚本（符号链接）和锁文件
setup_mock_project() {
  local project_dir="$1"
  local lock_file="$2"
  mkdir -p "$project_dir/native/config" "$project_dir/native/scripts"
  ln -sf "$BUILD_SCRIPT" "$project_dir/native/scripts/build-libmpv-controlled.sh"
  cp "$lock_file" "$project_dir/native/config/sources.lock.json"
  # 创建模拟工具脚本（空但可执行）
  for tool in generate-libmpv-manifest.sh generate-sbom.sh audit-licenses.sh collect-licenses.sh audit-libmpv-elf.sh; do
    printf '#!/usr/bin/env bash\n' > "$project_dir/native/scripts/$tool"
    chmod +x "$project_dir/native/scripts/$tool"
  done
}

# 通过 mock 项目调用构建脚本（使符号链接解析到 mock 项目根目录）
run_mock_build() {
  local project_dir="$1"
  local source_dir="$2"
  local output_dir="$3"
  local skip_compile="${4:-false}"
  local args=(--source "$source_dir" --output "$output_dir")
  [ "$skip_compile" = "true" ] && args+=(--skip-compile)
  (cd "$project_dir" && "$project_dir/native/scripts/build-libmpv-controlled.sh" "${args[@]}")
}

main() {
  local temp_dir source_dir output_dir lock_file project_dir

  echo "=== 测试 1：缺少来源锁文件必须失败 ==="
  temp_dir="$(setup_temp)"
  project_dir="$temp_dir/project"
  mkdir -p "$project_dir/native/scripts"
  ln -sf "$BUILD_SCRIPT" "$project_dir/native/scripts/build-libmpv-controlled.sh"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir"
  # 不创建锁文件
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail '缺少来源锁文件必须非零退出'
  fi

  echo "=== 测试 2：缺少受控源码目录必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  output_dir="$temp_dir/output"
  # source_dir 不存在
  if run_mock_build "$project_dir" "$temp_dir/nonexistent" "$output_dir" 2>/dev/null; then
    fail '缺少受控源码目录必须非零退出'
  fi

  echo "=== 测试 3：缺少组件目录必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/ffmpeg" "$source_dir/samba"
  # 缺少 mpv 目录
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail '缺少组件目录必须非零退出'
  fi

  echo "=== 测试 4：缺少 FFmpeg 配置证明必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  # 缺少 configure-options.txt
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail '缺少 FFmpeg 配置证明必须非零退出'
  fi

  echo "=== 测试 5：FFmpeg 配置未启用 libsmbclient 必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  echo '--disable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail 'FFmpeg 配置未启用 libsmbclient 必须非零退出'
  fi

  echo "=== 测试 6：Samba 依赖闭包未锁定必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  python3 -c "
import json
with open('$lock_file', encoding='utf-8') as f:
    lock = json.load(f)
lock['sources']['samba']['build']['dependencyClosureStatus'] = 'partial'
with open('$lock_file', 'w', encoding='utf-8') as f:
    json.dump(lock, f, ensure_ascii=False, indent=2)
"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  echo '--enable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail 'Samba 依赖闭包未锁定必须非零退出'
  fi

  echo "=== 测试 7：缺少 PKG_CONFIG_LIBDIR 必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  echo '--enable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  # 清空 PKG_CONFIG_LIBDIR
  unset PKG_CONFIG_LIBDIR
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" 2>/dev/null; then
    fail '缺少 PKG_CONFIG_LIBDIR 必须非零退出'
  fi

  echo "=== 测试 8：缺少已构建的 libmpv.so 必须失败 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  echo '--enable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  export PKG_CONFIG_LIBDIR="$temp_dir/sysroot"
  # 缺少 libmpv.so
  if run_mock_build "$project_dir" "$source_dir" "$output_dir" true 2>/dev/null; then
    fail '缺少已构建的 libmpv.so 必须非零退出'
  fi

  echo "=== 测试 9：正常路径（跳过编译）必须通过 ==="
  temp_dir="$(setup_temp)"
  lock_file="$temp_dir/sources.lock.json"
  create_minimal_lock "$lock_file"
  project_dir="$temp_dir/project"
  setup_mock_project "$project_dir" "$lock_file"
  source_dir="$temp_dir/source"
  output_dir="$temp_dir/output"
  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  echo '--enable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  touch "$source_dir/libmpv.so"  # 模拟已构建的库
  export PKG_CONFIG_LIBDIR="$temp_dir/sysroot"
  if ! run_mock_build "$project_dir" "$source_dir" "$output_dir" true; then
    fail '正常路径（跳过编译）必须通过'
  fi

  echo 'T057：受控离线构建失败测试通过。'
}

main "$@"
