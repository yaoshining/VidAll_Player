#!/usr/bin/env bash
# T055：完整不可变 sources lock 校验测试。
# 缺传递依赖、浮动版本、SHA/许可证/工具链缺失、缺补丁/子模块/构建开关必须非零退出。
# 覆盖正常路径（完整锁通过）、边界（字段格式）、失败路径（各项缺失均阻断）。
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly LOCK_FILE="$PROJECT_ROOT/native/config/sources.lock.json"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

# validate_lock <lock.json>：内联完整 schema 校验。非零表示锁不完整。
validate_lock() {
  python3 - "$1" <<'PY'
import json
import re
import sys

COMMIT_RE = re.compile(r'^[0-9a-f]{40}$')
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')

with open(sys.argv[1], encoding='utf-8') as handle:
    lock = json.load(handle)

errors = []

if lock.get('schemaVersion') != 3:
    errors.append('schemaVersion 必须为 3')

sources = lock.get('sources', {})
if not sources:
    errors.append('sources 不得为空')

required_core = ['mpv', 'ffmpeg', 'samba', 'gnutls', 'popt', 'libass', 'dav1d',
                 'mbedtls', 'libplacebo', 'freetype', 'harfbuzz', 'fribidi',
                 'fontconfig', 'lua', 'zlib']
missing_core = [s for s in required_core if s not in sources]
if missing_core:
    errors.append(f'缺少核心锁定来源：{missing_core}')

for name, src in sources.items():
    if not isinstance(src, dict):
        errors.append(f'{name} 必须为对象')
        continue
    if not src.get('repository'):
        errors.append(f'{name} 缺少 repository')
    commit = src.get('commit', '')
    if not COMMIT_RE.match(commit):
        errors.append(f'{name} 未锁定到 40 位 commit SHA（浮动版本禁止）：{commit!r}')
    if not src.get('license'):
        errors.append(f'{name} 缺少 license')
    if not src.get('purpose'):
        errors.append(f'{name} 缺少 purpose')
    fetch = src.get('fetchMethod', 'git-checkout')
    if fetch == 'archive':
        archive = src.get('archiveSha256', '')
        if not SHA256_RE.match(archive):
            errors.append(f'{name} archive 方式缺少 64 位 archiveSha256')
    elif fetch != 'git-checkout':
        errors.append(f'{name} fetchMethod 必须为 git-checkout 或 archive')

# 子模块：每个可能含子模块的来源须声明 submodule 列表（可为空数组）
submodules = lock.get('submodules', {})
if not isinstance(submodules, dict):
    errors.append('submodules 必须为对象')
for name in ('mpv', 'ffmpeg'):
    if name in sources and name not in submodules:
        errors.append(f'{name} 须声明 submodules 列表（无子模块时为空数组）')

# 补丁：每个补丁须锁定路径与 SHA-256；项目已有补丁，不得为空
patches = lock.get('patches', [])
if not isinstance(patches, list):
    errors.append('patches 必须为数组')
if not patches:
    errors.append('patches 不得为空（项目已存在受控补丁）')
for patch in patches:
    if not patch.get('path'):
        errors.append('补丁缺少 path')
    if not SHA256_RE.match(patch.get('sha256', '')):
        errors.append(f'补丁 {patch.get("path")} 缺少 64 位 sha256')
    if not patch.get('appliesTo'):
        errors.append(f'补丁 {patch.get("path")} 缺少 appliesTo')

# 工具链：每个工具须锁定版本与 SHA-256/摘要（字符串 sha256 或多平台 digests 对象）
tools = lock.get('tools', {})
if not tools:
    errors.append('tools 不得为空')
for tool_name, tool in tools.items():
    if not isinstance(tool, dict):
        errors.append(f'工具 {tool_name} 必须为对象（含 version 与 sha256/digests）')
        continue
    if not tool.get('version'):
        errors.append(f'工具 {tool_name} 缺少 version')
    sha = tool.get('sha256')
    digests = tool.get('digests')
    if not (SHA256_RE.match(sha or '') or (isinstance(digests, dict) and all(SHA256_RE.match(v) for v in digests.values()))):
        errors.append(f'工具 {tool_name} 缺少有效 sha256 或 digests（不可复现工具链）')

# 构建开关
build_switches = lock.get('buildSwitches', {})
if not isinstance(build_switches, dict):
    errors.append('buildSwitches 必须为对象')
if not build_switches.get('targetAbi'):
    errors.append('buildSwitches 缺少 targetAbi')
if not build_switches.get('linkage'):
    errors.append('buildSwitches 缺少 linkage')
if not build_switches.get('gpl'):
    errors.append('buildSwitches 缺少 gpl 开关')

# 许可证策略
policy = lock.get('licensePolicy', {})
if not policy.get('releaseRequiresReview'):
    errors.append('licensePolicy 缺少 releaseRequiresReview')
if policy.get('noticeRequired') is not True:
    errors.append('licensePolicy.noticeRequired 必须为 true')
if policy.get('sourceOfferRequired') is not True:
    errors.append('licensePolicy.sourceOfferRequired 必须为 true')

# 传递依赖：声明 dependencyClosureStatus=complete 的来源须列出全部传递依赖并锁定
for name, src in sources.items():
    build = src.get('build') if isinstance(src, dict) else None
    if isinstance(build, dict) and build.get('dependencyClosureStatus') == 'complete':
        transitive = build.get('transitiveDependencies', [])
        if not transitive:
            errors.append(f'{name} 声明闭包完成但缺少 transitiveDependencies')
        for dep in transitive:
            if dep not in sources:
                errors.append(f'{name} 的传递依赖 {dep} 未在 sources 中锁定')

if errors:
    for msg in errors:
        print(f'  - {msg}', file=sys.stderr)
    raise SystemExit(1)
PY
}

# --- 正常路径：完整合成锁必须通过 ---
write_complete_fixture() {
  python3 - "$1" <<'PY'
import json
import sys

# 合成完整锁：每个来源均含 40 位 commit、license、purpose 与 64 位 archiveSha256。
sources = {
    'mpv': {'repository': 'https://example.invalid/mpv.git', 'tag': 'v0.40.0', 'commit': '287d7cdb78975ae350d7c2a287eae3c2072c93f7', 'license': 'GPL-2.0-or-later', 'purpose': 'libmpv 核心', 'fetchMethod': 'archive', 'archiveSha256': '1' * 64},
    'ffmpeg': {'repository': 'https://example.invalid/ffmpeg.git', 'tag': 'n7.1.1', 'commit': 'a1328e68877e12ab5a6e5d92a84aefa566783ea5', 'license': 'LGPL-2.1-or-later', 'purpose': '解封装', 'fetchMethod': 'archive', 'archiveSha256': '2' * 64},
    'samba': {'repository': 'https://example.invalid/samba.git', 'tag': 'samba-4.20.7', 'commit': '3984b04d7085c428ab3126ef4cfac2a396b5b29e', 'license': 'GPL-3.0-or-later', 'purpose': 'libsmbclient', 'fetchMethod': 'archive', 'archiveSha256': '3' * 64, 'build': {'target': 'aarch64-linux-ohos', 'pkgConfigModule': 'smbclient', 'linkage': 'static', 'dependencyClosureStatus': 'complete', 'transitiveDependencies': ['zlib', 'popt', 'gnutls']}},
    'gnutls': {'repository': 'https://example.invalid/gnutls.git', 'tag': '3.8.7', 'commit': '994d9392a607308e452ecae87caafd6ea81288f3', 'license': 'LGPL-2.1-or-later', 'purpose': 'TLS', 'fetchMethod': 'git-checkout'},
    'popt': {'repository': 'https://example.invalid/popt.git', 'tag': 'popt-1.19-release', 'commit': '916e61045d268f7e37ade5ec047eb77e8299e6ad', 'license': 'MIT', 'purpose': '命令行', 'fetchMethod': 'git-checkout'},
    'libass': {'repository': 'https://example.invalid/libass.git', 'tag': '0.17.3', 'commit': '01ae90a8028545704848fcb19b680ccb3964948d', 'license': 'ISC', 'purpose': '字幕', 'fetchMethod': 'git-checkout'},
    'dav1d': {'repository': 'https://example.invalid/dav1d.git', 'tag': '1.5.0', 'commit': '27ed87f37977ea73782ccf7a2b59492a24c87d4e', 'license': 'BSD-2-Clause', 'purpose': 'AV1', 'fetchMethod': 'git-checkout'},
    'mbedtls': {'repository': 'https://example.invalid/mbedtls.git', 'tag': 'mbedtls-3.6.2', 'commit': '34e66e1b7b97f9dc69c19f6f14c9f91e588dc31a', 'license': 'Apache-2.0', 'purpose': 'TLS', 'fetchMethod': 'git-checkout'},
    'libplacebo': {'repository': 'https://example.invalid/libplacebo.git', 'tag': 'v7.349.0', 'commit': '9c4b6bbd7a1e223ffdd61affc4e5d463d42d4345', 'license': 'LGPL-2.1-or-later', 'purpose': '渲染', 'fetchMethod': 'git-checkout'},
    'freetype': {'repository': 'https://example.invalid/freetype.git', 'tag': 'VER-2-13-3', 'commit': '534ad3456055ee1f65ecde3bcf22a656a31514d1', 'license': 'FTL', 'purpose': '字体', 'fetchMethod': 'git-checkout'},
    'harfbuzz': {'repository': 'https://example.invalid/harfbuzz.git', 'tag': '10.2.0', 'commit': '818890f8f6c364ed111689a40ad510c415e559a1', 'license': 'MIT', 'purpose': '文字整形', 'fetchMethod': 'git-checkout'},
    'fribidi': {'repository': 'https://example.invalid/fribidi.git', 'tag': 'v1.0.16', 'commit': '9123b467f080c7ea15509bd7cbd457817544a7e1', 'license': 'LGPL-2.1-or-later', 'purpose': '双向文本', 'fetchMethod': 'git-checkout'},
    'fontconfig': {'repository': 'https://example.invalid/fontconfig.git', 'tag': '2.16.0', 'commit': 'fca6349c9a9ca4b0b14233de6e178909a4f44843', 'license': 'MIT', 'purpose': '字体配置', 'fetchMethod': 'git-checkout'},
    'lua': {'repository': 'https://example.invalid/lua.git', 'tag': 'v5.4.7', 'commit': '1ab3208a1fceb12fca8f24ba57d6e13c5bff15e3', 'license': 'MIT', 'purpose': '脚本运行时', 'fetchMethod': 'git-checkout'},
    'zlib': {'repository': 'https://example.invalid/zlib.git', 'tag': 'v1.3.1', 'commit': '925af44f3cde53c6b076611c297850091b5dc7bb', 'license': 'Zlib', 'purpose': '压缩', 'fetchMethod': 'git-checkout'},
}
lock = {
    'schemaVersion': 3,
    'sources': sources,
    'submodules': {'mpv': [], 'ffmpeg': []},
    'patches': [{'path': 'native/patches/libmpv-ohos-build/0001.patch', 'sha256': 'a' * 64, 'appliesTo': 'mpv'}],
    'tools': {'meson': {'version': '1.7.0', 'sha256': 'ae3f12953045f3c7c60e27f2af1ad862f14dee125b4ed9bcb8a842a5080dbf85'}, 'ninja': {'version': '1.11.1', 'digests': {'macosx-arm64': 'b' * 64, 'manylinux-x86_64': 'c' * 64}}},
    'buildSwitches': {'targetAbi': 'aarch64-linux-ohos', 'linkage': 'static', 'gpl': True},
    'licensePolicy': {'releaseRequiresReview': ['GPL-2.0-or-later', 'GPL-3.0-or-later', 'LGPL-2.1-or-later'], 'noticeRequired': True, 'sourceOfferRequired': True},
}
with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump(lock, handle, ensure_ascii=False, indent=2)
PY
}

main() {
  [ -f "$LOCK_FILE" ] || fail "未找到来源锁：$LOCK_FILE"

  # --- 失败路径：合成锁逐项缺失必须非零 ---
  local temp_dir fixture
  temp_dir="$(mktemp -d)"
  trap "rm -rf '$temp_dir'" EXIT

  # 1) 完整合成锁必须通过（正常路径）
  write_complete_fixture "$temp_dir/complete.lock.json"
  validate_lock "$temp_dir/complete.lock.json" || fail '完整合成锁必须通过校验'

  # 2) 浮动版本（缺 commit）必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
d["sources"]["mpv"]["commit"] = "v0.40.0"
json.dump(d, open("'"$temp_dir"'/floating.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/floating.lock.json"; then
    fail '浮动版本（非 40 位 commit）必须非零退出'
  fi

  # 3) 缺少 archiveSha256 必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
del d["sources"]["mpv"]["archiveSha256"]
json.dump(d, open("'"$temp_dir"'/no-archive-sha.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-archive-sha.lock.json"; then
    fail '缺少 archiveSha256 必须非零退出'
  fi

  # 4) 缺少 license 必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
del d["sources"]["ffmpeg"]["license"]
json.dump(d, open("'"$temp_dir"'/no-license.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-license.lock.json"; then
    fail '缺少 license 必须非零退出'
  fi

  # 5) 缺少工具链 SHA 必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
del d["tools"]["meson"]["sha256"]
json.dump(d, open("'"$temp_dir"'/no-tool-sha.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-tool-sha.lock.json"; then
    fail '缺少工具链 SHA 必须非零退出'
  fi

  # 6) 缺少补丁必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
d["patches"] = []
json.dump(d, open("'"$temp_dir"'/no-patches.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-patches.lock.json"; then
    fail '缺少补丁锁定必须非零退出'
  fi

  # 7) 缺少子模块声明必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
del d["submodules"]
json.dump(d, open("'"$temp_dir"'/no-submodules.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-submodules.lock.json"; then
    fail '缺少子模块声明必须非零退出'
  fi

  # 8) 缺少构建开关必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
del d["buildSwitches"]
json.dump(d, open("'"$temp_dir"'/no-switches.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/no-switches.lock.json"; then
    fail '缺少构建开关必须非零退出'
  fi

  # 9) 传递依赖未锁定必须失败
  python3 -c '
import json
d = json.load(open("'"$temp_dir"'/complete.lock.json"))
d["sources"]["samba"]["build"]["transitiveDependencies"].append("unlisted-dep")
json.dump(d, open("'"$temp_dir"'/unlisted-transitive.lock.json", "w"), ensure_ascii=False)
'
  if validate_lock "$temp_dir/unlisted-transitive.lock.json"; then
    fail '未锁定的传递依赖必须非零退出'
  fi

  # --- 真实来源锁必须通过（T056 实现后转绿）---
  validate_lock "$LOCK_FILE" || fail '真实来源锁不完整：缺传递依赖、SHA、许可证、工具链、补丁、子模块或构建开关'

  echo 'T055：sources.lock 完整性校验通过。'
}

main "$@"
