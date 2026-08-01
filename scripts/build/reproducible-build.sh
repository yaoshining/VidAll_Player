#!/usr/bin/env bash
# T058: 可复现离线构建入口。候选链路只接受已锁定并已校验的输入。
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly LOCK_FILE="$PROJECT_ROOT/native/config/sources.lock.json"
readonly DEFAULT_CACHE_DIR="${REPRODUCIBLE_CACHE_DIR:-$PROJECT_ROOT/.reproducible-cache}"
readonly DEFAULT_BUILD_DIR="${REPRODUCIBLE_BUILD_DIR:-$PROJECT_ROOT/build}"
readonly TARGET_ABI="aarch64-linux-ohos"

usage() {
  cat >&2 <<EOF_USAGE
用法: $0 [选项]
  --cache-dir <目录>  来源缓存目录
  --build-dir <目录>  构建输出目录
  --skip-download     只校验现有缓存，不访问网络
  --skip-patch        不应用补丁
  --skip-build        完成输入校验后退出，不执行构建
EOF_USAGE
  exit 2
}

cache_dir="$DEFAULT_CACHE_DIR"
build_dir="$DEFAULT_BUILD_DIR"
skip_download=false
skip_patch=false
skip_build=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cache-dir) [ "$#" -ge 2 ] || usage; cache_dir="$2"; shift 2 ;;
    --build-dir) [ "$#" -ge 2 ] || usage; build_dir="$2"; shift 2 ;;
    --skip-download) skip_download=true; shift ;;
    --skip-patch) skip_patch=true; shift ;;
    --skip-build) skip_build=true; shift ;;
    --help) usage ;;
    *) echo "未知选项: $1" >&2; usage ;;
  esac
done

[ -f "$LOCK_FILE" ] || { echo "错误: 来源锁不存在: $LOCK_FILE" >&2; exit 1; }

verify_sha256() {
  local file="$1" expected="$2" actual
  [ -f "$file" ] || { echo "错误: 缓存归档不存在: $file" >&2; return 1; }
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$file" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$file" | awk '{print $1}')"
  else
    echo "错误: 需要 sha256sum 或 shasum" >&2; return 1
  fi
  [ "$actual" = "$expected" ] || { echo "错误: SHA-256 不匹配: $file" >&2; return 1; }
}

validate_lock() {
  python3 - "$LOCK_FILE" <<'PY'
import json, re, sys
lock = json.load(open(sys.argv[1], encoding='utf-8'))
sha = re.compile(r'^[0-9a-f]{64}$')
commit = re.compile(r'^[0-9a-f]{40}$')
for name, source in lock.get('sources', {}).items():
    revision = source.get('commit', '')
    if not commit.fullmatch(revision) or set(revision) == {'0'}:
        raise SystemExit(f'错误: {name} 没有有效 commit 锁定')
    if source.get('fetchMethod', 'git-checkout') == 'archive':
        digest = source.get('archiveSha256', '')
        if not sha.fullmatch(digest) or set(digest) == {'0'} or not source.get('archiveUrl'):
            raise SystemExit(f'错误: {name} 缺少可信 archiveUrl 或 archiveSha256')
    if 'example.invalid' in source.get('repository', ''):
        raise SystemExit(f'错误: {name} 使用占位来源')
PY
}

fetch_sources() {
  python3 - "$LOCK_FILE" "$cache_dir" "$skip_download" <<'PY'
import hashlib, json, pathlib, subprocess, sys, urllib.request
lock_path, cache_dir, offline = sys.argv[1:]
lock = json.load(open(lock_path, encoding='utf-8'))
root = pathlib.Path(cache_dir) / 'sources'
root.mkdir(parents=True, exist_ok=True)
for name, source in lock.get('sources', {}).items():
    method = source.get('fetchMethod', 'git-checkout')
    destination = root / name
    if method == 'git-checkout':
        if offline == 'true' and not destination.is_dir():
            raise SystemExit(f'错误: 离线缓存缺少来源: {name}')
        if not destination.is_dir():
            subprocess.run(['git', 'clone', '--no-checkout', source['repository'], str(destination)], check=True)
        subprocess.run(['git', '-C', str(destination), 'fetch', '--depth', '1', 'origin', source['commit']], check=True)
        subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', '--force', source['commit']], check=True)
    elif method == 'archive':
        archive = root / f'{name}.archive'
        if not archive.is_file():
            if offline == 'true':
                raise SystemExit(f'错误: 离线缓存缺少归档: {name}')
            url = source.get('archiveUrl')
            if not url:
                raise SystemExit(f'错误: {name} 缺少 archiveUrl')
            urllib.request.urlretrieve(url, archive)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != source['archiveSha256']:
            raise SystemExit(f'错误: {name} 归档 SHA-256 不匹配')
    else:
        raise SystemExit(f'错误: {name} 使用未知 fetchMethod: {method}')
PY
}

verify_patches() {
  python3 - "$LOCK_FILE" "$PROJECT_ROOT" <<'PY'
import hashlib, json, pathlib, sys
lock, root = json.load(open(sys.argv[1], encoding='utf-8')), pathlib.Path(sys.argv[2])
for patch in lock.get('patches', []):
    path = root / patch['path']
    if not path.is_file(): raise SystemExit(f'错误: 补丁不存在: {path}')
    if hashlib.sha256(path.read_bytes()).hexdigest() != patch['sha256']:
        raise SystemExit(f'错误: 补丁 SHA-256 不匹配: {path}')
PY
}

main() {
  validate_lock
  mkdir -p "$cache_dir" "$build_dir"
  fetch_sources
  if [ "$skip_patch" = false ]; then verify_patches; fi
  if [ "$skip_build" = true ]; then
    echo "输入校验完成，按 --skip-build 未执行构建。"
    return 0
  fi
  echo "错误: 未实现真实 aarch64-linux-ohos 交叉编译；拒绝生成模拟 libmpv.so。" >&2
  exit 1
}
main
