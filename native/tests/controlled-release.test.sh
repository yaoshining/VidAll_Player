#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly LOCK_FILE="$PROJECT_ROOT/native/config/sources.lock.json"
readonly CONTROLLED_BUILD="$PROJECT_ROOT/native/scripts/build-libmpv-controlled.sh"
readonly MANIFEST_TOOL="$PROJECT_ROOT/native/scripts/generate-libmpv-manifest.sh"
readonly SBOM_TOOL="$PROJECT_ROOT/native/scripts/generate-sbom.sh"
readonly LICENSE_TOOL="$PROJECT_ROOT/native/scripts/audit-licenses.sh"
readonly ELF_AUDIT_TOOL="$PROJECT_ROOT/native/scripts/audit-libmpv-elf.sh"
readonly REPRODUCIBILITY_TOOL="$PROJECT_ROOT/native/scripts/verify-reproducible-artifacts.sh"
readonly NOTICE_TOOL="$PROJECT_ROOT/native/scripts/collect-licenses.sh"
readonly CAPABILITY_EVIDENCE_VALIDATOR="$PROJECT_ROOT/native/scripts/validate-capability-evidence.sh"
readonly CAPABILITY_EVIDENCE="$PROJECT_ROOT/release/capabilities/arm64-tv-capability-evidence.json"

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

assert_json() {
  python3 - "$1" <<'PY'
import json
import sys
with open(sys.argv[1], encoding='utf-8') as f:
    json.load(f)
PY
}

main() {
  local temp_dir output_dir source_dir
  temp_dir="$(mktemp -d)"
  trap "rm -rf '$temp_dir'" EXIT
  output_dir="$temp_dir/output"
  source_dir="$temp_dir/source"

  test -x "$CONTROLLED_BUILD" || fail "缺少受控构建脚本"
  test -x "$MANIFEST_TOOL" || fail "缺少构建清单工具"
  test -x "$SBOM_TOOL" || fail "缺少 SBOM 工具"
  test -x "$LICENSE_TOOL" || fail "缺少许可证审计工具"
  test -x "$ELF_AUDIT_TOOL" || fail "缺少 ELF 审计工具"
  test -x "$REPRODUCIBILITY_TOOL" || fail "缺少可重复构建验证工具"
  test -x "$NOTICE_TOOL" || fail "缺少许可证收集工具"
  test -x "$CAPABILITY_EVIDENCE_VALIDATOR" || fail "缺少能力证据校验工具"
  test -f "$CAPABILITY_EVIDENCE" || fail "缺少 ARM64 TV 能力证据"
  "$CAPABILITY_EVIDENCE_VALIDATOR" --input "$CAPABILITY_EVIDENCE"

  assert_json "$LOCK_FILE"
  python3 - "$LOCK_FILE" <<'PY'
import json
import re
import sys
lock = json.load(open(sys.argv[1], encoding='utf-8'))
required = {'mpv', 'ffmpeg', 'samba', 'gnutls', 'popt', 'libass', 'dav1d', 'mbedtls', 'libplacebo', 'dovi_tools', 'freetype', 'harfbuzz', 'fribidi', 'fontconfig', 'lua', 'zlib'}
sources = lock.get('sources', {})
missing = required - set(sources)
assert not missing, f'缺少锁定来源：{sorted(missing)}'
for name, value in sources.items():
    assert re.fullmatch(r'[0-9a-f]{40}', value.get('commit', '')), f'{name} 未锁定到 commit SHA'
samba_build = sources['samba'].get('build', {})
assert samba_build.get('pkgConfigModule') == 'smbclient'
assert samba_build.get('dependencyClosureStatus') == 'complete', 'Samba 依赖闭包必须已交叉构建验证完成'
assert samba_build.get('linkage') == 'static', 'libsmbclient 必须静态链接进最终制品'
policy = lock.get('licensePolicy', {})
assert 'GPL-3.0-or-later' in policy.get('releaseRequiresReview', []), 'Samba GPLv3 必须阻断未经审查的发布'
PY

  mkdir -p "$source_dir/mpv" "$source_dir/ffmpeg" "$source_dir/samba"
  printf '%s\n' '--enable-static' '--disable-shared' '--enable-gpl' '--enable-demuxer=dash' '--enable-libsmbclient' > "$source_dir/ffmpeg/configure-options.txt"
  printf '%s\n' '-Dgpl=true' '-Dohos=enabled' > "$source_dir/mpv/meson-options.txt"
  printf '%s\n' 'dash' 'hls' > "$source_dir/ffmpeg/demuxers.txt"
  printf '%s\n' 'https' 'http' 'libsmbclient' > "$source_dir/ffmpeg/protocols.txt"
  printf '%s\n' 'h264' 'hevc' > "$source_dir/ffmpeg/decoders.txt"
  printf '%s\n' 'png' > "$source_dir/ffmpeg/encoders.txt"
  printf '%s\n' 'scale' > "$source_dir/ffmpeg/filters.txt"
  printf '%s\n' 'libc++.so' 'libhilog_ndk.z.so' > "$source_dir/dynamic-dependencies.txt"

  "$MANIFEST_TOOL" --lock "$LOCK_FILE" --source "$source_dir" --output "$output_dir/feature-manifest.json" --abi arm64-v8a --min-sdk 15 --build-time 0
  assert_json "$output_dir/feature-manifest.json"
  python3 - "$output_dir/feature-manifest.json" <<'PY'
import json
import sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
assert m['abi'] == 'arm64-v8a'
assert m['minSdk'] == 15
assert m['buildTime'] == '1970-01-01T00:00:00Z'
assert '--enable-gpl' in m['ffmpeg']['configureOptions']
assert '--enable-libsmbclient' in m['ffmpeg']['configureOptions']
assert m['ffmpeg']['components']['demuxers'] == ['dash', 'hls']
assert 'libsmbclient' in m['ffmpeg']['components']['protocols']
assert m['mpv']['mesonOptions'] == ['-Dgpl=true', '-Dohos=enabled']
assert m['dynamicDependencies'] == ['libc++.so', 'libhilog_ndk.z.so']
PY

  "$SBOM_TOOL" --lock "$LOCK_FILE" --format spdx --output "$output_dir/sbom.spdx.json"
  "$SBOM_TOOL" --lock "$LOCK_FILE" --format cyclonedx --output "$output_dir/sbom.cdx.json"
  assert_json "$output_dir/sbom.spdx.json"
  assert_json "$output_dir/sbom.cdx.json"
  python3 - "$output_dir/sbom.spdx.json" "$output_dir/sbom.cdx.json" <<'PY'
import json
import sys
spdx = json.load(open(sys.argv[1], encoding='utf-8'))
cdx = json.load(open(sys.argv[2], encoding='utf-8'))
assert spdx['spdxVersion'] == 'SPDX-2.3'
assert any(p['name'] == 'ffmpeg' for p in spdx['packages'])
assert cdx['bomFormat'] == 'CycloneDX'
assert any(c['name'] == 'mpv' for c in cdx['components'])
PY

  "$LICENSE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/license-audit.json"
  "$NOTICE_TOOL" --lock "$LOCK_FILE" --output "$output_dir/NOTICE"
  test -s "$output_dir/NOTICE" || fail '许可证 NOTICE 不得为空'
  assert_json "$output_dir/license-audit.json"
  python3 - "$output_dir/license-audit.json" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding='utf-8'))
assert r['status'] == 'review-required'
assert any(i['license'].startswith('GPL') for i in r['reviewRequired'])
PY

  if "$ELF_AUDIT_TOOL" --input "$temp_dir/missing.so" --output "$output_dir/elf-audit.json"; then
    fail 'ELF 审计必须拒绝不存在的输入'
  fi

  local mock_bin
  mock_bin="$temp_dir/mock-bin"
  mkdir -p "$mock_bin"
  cat > "$mock_bin/readelf" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -d) printf ' 0x0000000000000001 (NEEDED)             Shared library: [libc++.so]\n' ;;
  --dyn-syms) python3 -c 'print("\n".join(f"    1: 00000000     0 FUNC    GLOBAL DEFAULT    1 symbol_{i:07d}" for i in range(300000)))' ;;
esac
EOF
  chmod +x "$mock_bin/readelf"
  : > "$temp_dir/mock-libmpv.so"
  PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-large.json" --allow libc++.so
  assert_json "$output_dir/elf-audit-large.json"
  python3 - "$output_dir/elf-audit-large.json" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
assert report['status'] == 'passed'
assert len(report['exportedDynamicSymbols']) == 299997
PY

  cat > "$mock_bin/readelf" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -d) printf ' 0x0000000000000001 (NEEDED)             Shared library: [libsmbclient.so]\n' ;;
  --dyn-syms) printf '    1: 00000000     0 FUNC    GLOBAL DEFAULT    1 fixture_symbol\n' ;;
esac
EOF
  chmod +x "$mock_bin/readelf"
  if PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-forbidden.json" --allow libsmbclient.so --forbid libsmbclient.so; then
    fail 'ELF 审计必须拒绝动态链接的 libsmbclient.so'
  fi
  python3 - "$output_dir/elf-audit-forbidden.json" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
assert report['status'] == 'failed'
assert report['forbiddenNeededLibraries'] == ['libsmbclient.so']
PY

  grep -Fq 'sbom.cdx.json' "$CONTROLLED_BUILD" || fail '受控构建必须使用统一的 CycloneDX SBOM 文件名'
  grep -Fq 'sbom.cdx.json' "$PROJECT_ROOT/.github/workflows/build-libmpv.yml" || fail 'CI 必须使用统一的 CycloneDX SBOM 文件名'
  grep -Fq 'mkdir -p "$SAMBA_DIR/bin"' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '复制 host 工具前必须创建交叉树 bin 目录'
  grep -Fq "if not bld.env.CROSS_COMPILE:" "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '交叉构建必须从 Waf 图中移除 HostCC 子系统'
  grep -Fq "not bld.env.CROSS_COMPILE and not bld.CONFIG_SET('USING_SYSTEM_ASN1_COMPILE')" "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '交叉构建必须复用预编译的 asn1_compile'
  grep -Fq "not bld.env.CROSS_COMPILE and not bld.CONFIG_SET('USING_SYSTEM_COMPILE_ET')" "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '交叉构建必须复用预编译的 compile_et'
  grep -Fq 'assert s.count(old_asn1) == 2' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail 'ASN.1 helper 和 HostCC 目标必须同时从交叉图移除'
  grep -Fq 'assert s.count(old_compile_et) == 2' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '错误表 helper 和 HostCC 目标必须同时从交叉图移除'
  grep -Fq "#if defined(DARWINOS) && !defined(__OHOS__)" "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '交叉构建不得注册依赖 CoreFoundation 的 MACOSXFS 编码器'
  grep -Fq 'assert s.count(old) == 3' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail 'ethtool 补丁必须覆盖 Samba 4.20.7 的三处条件块'
  grep -Fq '#if defined(HAVE_ETHTOOL) && !defined(__OHOS__)' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail 'OHOS 交叉构建不得链接不完整的 Linux ethtool API'
  grep -Fq 'export PKG_CONFIG_BIN="$(command -v pkg-config)"' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail '必须导出宿主 pkg-config 的实际位置给包装器'
  grep -Fq 'exec "$PKG_CONFIG_BIN" --static "$@"' "$PROJECT_ROOT/native/scripts/build-libsmbclient-controlled.sh" || fail 'Samba 必须解析 GnuTLS 静态传递依赖'
  grep -Fq -- '--enable-gpl' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0003-ffmpeg-enable-libxml2-dash-demuxer.patch" || fail 'FFmpeg 补丁必须启用 GPL'
  grep -Fq -- '--enable-libsmbclient' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0003-ffmpeg-enable-libxml2-dash-demuxer.patch" || fail 'FFmpeg 补丁必须启用 libsmbclient'
  grep -Fq -- '--pkg-config-flags=--static' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0003-ffmpeg-enable-libxml2-dash-demuxer.patch" || fail 'FFmpeg 必须静态解析 libsmbclient 传递依赖'
  grep -Fq -- '-Dgpl=true' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0004-mpv-meson-wipe-reconfigure.patch" || fail 'mpv 补丁必须启用 GPL'
  grep -Fq -- '-Dopensles=disabled' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0004-mpv-meson-wipe-reconfigure.patch" || fail 'mpv 补丁必须基于锁定上游脚本并保留 OpenSLES 配置'
  grep -Fq -- '-Dmanpage-build=disabled' "$PROJECT_ROOT/native/patches/libmpv-ohos-build/0004-mpv-meson-wipe-reconfigure.patch" || fail 'mpv 补丁必须保留锁定上游的构建末尾配置'

  python3 - "$PROJECT_ROOT/.github/workflows/build-libmpv.yml" <<'PY'
from pathlib import Path
import sys

workflow = Path(sys.argv[1]).read_text(encoding='utf-8')
assert 'cross-build-prerequisites:' in workflow, 'CI 必须声明交叉构建前置条件任务'
assert 'runs-on: [self-hosted, macos, deveco]' in workflow, '交叉构建前置条件必须使用受控 DevEco 运行器'
assert 'dependencyClosureStatus' in workflow, 'CI 必须在构建前验证 Samba 依赖闭包'
assert 'PKG_CONFIG_LIBDIR' in workflow, 'CI 必须验证隔离的 OpenHarmony pkg-config 目录'
assert 'build-libmpv-controlled.sh' in workflow, 'CI 必须调用受控发布门禁'
assert 'libmpv-cross-build-prerequisites' in workflow, 'CI 必须上传交叉构建前置条件审计制品'
assert 'inputs.run_cross_build' in workflow, 'CI 必须保留手动受控调度入口'
assert 'detect-build-changes' in workflow, 'CI 必须检测构建脚本变更以按需触发交叉构建'
assert 'cache-hit' in workflow, 'CI 必须对 libsmbclient 交叉构建启用缓存命中跳过'
assert 'force_build' in workflow, 'CI 必须支持强制重建入口'
assert 'build-libmpv-with-smb:' in workflow, 'CI 必须在 libsmbclient 成功后执行真实 libmpv 交叉构建'
assert 'needs: [native-contracts, detect-build-changes, build-libsmbclient]' in workflow, '真实 libmpv 构建必须依赖同次运行的 libsmbclient 制品'
assert 'name: libsmbclient-ohos-sysroot' in workflow, '真实 libmpv 构建必须下载同次运行的 SMB sysroot 制品'
assert 'actions: read' in workflow, 'CI 必须授权读取同次构建的 artifact'
assert '直接下载并解压同次 SMB sysroot' in workflow, '真实 libmpv 构建必须直接下载并解压 SMB artifact'
libmpv_job = workflow.split('  build-libmpv-with-smb:', 1)[1]
assert 'actions/runs/${GITHUB_RUN_ID}/artifacts' in libmpv_job, 'SMB artifact 必须从当前 workflow run 查询'
assert 'GITHUB_TOKEN: ${{ github.token }}' in libmpv_job, 'SMB artifact API 下载必须显式注入 GitHub token'
assert '--retry 5 --retry-all-errors' in libmpv_job, 'SMB artifact 下载必须重试临时传输中断'
assert 'unzip -tqq "$SMB_ARTIFACT_ZIP"' in libmpv_job, 'SMB artifact 必须先校验 zip 完整性'
assert 'unzip -q "$SMB_ARTIFACT_ZIP" -d "$SMB_DOWNLOAD_ROOT"' in libmpv_job, 'SMB artifact 必须完成解压后再读取元数据'
assert '"/Applications/DevEco-Studio.app/Contents/sdk/${HOS_SDK_VERSION:-10}/openharmony"' in libmpv_job, '真实 libmpv 构建必须复用带版本的 DevEco NDK 探测路径'
assert 'VIDALL_PLAYER_SMB_SYSROOT' in workflow, '真实 libmpv 构建必须向引导脚本注入 SMB sysroot'
assert 'SMB_DOWNLOAD_ROOT/lib/libsmbclient.a' in libmpv_job, '单个 SMB artifact 解压到目标目录时必须直接使用其根目录'
assert "-name 'libsmbclient.a'" in libmpv_job, 'artifact 保留顶层目录时必须回退定位静态库'
assert 'dirname "$SMB_ARCHIVE")/.."' in libmpv_job, '回退定位到 lib/libsmbclient.a 后必须向上一级得到 sysroot 根目录'
assert '未在下载制品中找到 libsmbclient.a' in libmpv_job, 'SMB sysroot 缺失时必须输出明确诊断'
assert 'SMB artifact root: $SMB_SYSROOT' in libmpv_job, 'SMB sysroot 校验必须输出定位后的根目录'
assert 'test -d "$SMB_DOWNLOAD_ROOT"' in libmpv_job, 'SMB sysroot 定位前必须校验下载目录'
assert '2>/dev/null || true' in libmpv_job, 'artifact 目录遍历失败时必须保留后续明确诊断'
assert 'libsmbclient.a 不可读或为空' in libmpv_job, 'SMB 静态库校验失败时必须输出明确诊断'
assert 'OHOS_NDK_HOME: ${{ env.OHOS_NDK }}' in workflow, '真实 libmpv 构建必须向上游脚本传递已验证的 OpenHarmony NDK'
assert '安装 libmpv Rust 与下载工具' in workflow, '真实 libmpv 构建必须预先安装 Rust 和下载工具'
assert 'curl --proto' in libmpv_job and 'sh -s -- -y --profile minimal --default-toolchain stable' in libmpv_job, '真实 libmpv 构建必须用 curl 安装 Rust，避免依赖可能损坏的 Homebrew formula'
assert 'wget shim' in libmpv_job and 'curl -fsSL --retry 5 --retry-all-errors "$url"' in libmpv_job, '上游缺少 wget 时必须提供带重试的 curl shim'
assert 'wget shim 仅支持 -qO <输出文件> <https-url>' in libmpv_job, 'wget shim 必须支持上游依赖归档下载'
assert 'output="$2"' in libmpv_job and 'url="$3"' in libmpv_job, 'wget shim 必须将输出文件与 URL 传给 curl'
assert 'curl -fsSL --retry 5 --retry-all-errors "$url" --output "$output"' in libmpv_job, '上游归档下载必须重试临时传输中断'
assert 'git shim 仅为 clone/fetch 重试瞬态网络故障' in libmpv_job, '上游依赖 git 下载必须重试瞬态网络故障'
assert 'for attempt in 1 2 3 4 5' in libmpv_job and 'rm -rf -- "$destination"' in libmpv_job, '失败的浅克隆必须清理后重试'
assert 'brew install wget rustup-init' not in libmpv_job, '真实 libmpv 构建不得依赖 Homebrew 安装 Rust 或 wget'
assert 'PATH: ${{ env.PATH }}:${{ runner.home }}/.cargo/bin' not in libmpv_job, '真实 libmpv 构建不得用空的 Actions env.PATH 覆盖系统 PATH'
assert 'build-libmpv-bootstrap.sh' in workflow, '真实 libmpv 构建必须执行受控引导脚本'
assert 'llvm-readelf' in workflow and "grep -F 'libsmbclient.so'" in workflow, '真实 libmpv 构建必须拒绝动态 libsmbclient.so'
assert 'libmpv-arm64-with-smb' in workflow, '真实 libmpv 构建必须上传 ARM64 SMB 制品'
assert "printf '%s\\n' -Dgpl=true" in workflow, 'CI 元数据必须声明 GPL 构建选项'
assert '-Dgpl=false' not in workflow, 'CI 不得再生成禁用 GPL 的 libmpv 元数据'
assert 'direct SMB 已可播放' not in workflow, 'CI 不得在未完成真机验证时宣称 direct SMB 可播放'
PY

  printf 'same artifact\n' > "$temp_dir/first.so"
  cp "$temp_dir/first.so" "$temp_dir/second.so"
  "$REPRODUCIBILITY_TOOL" --first "$temp_dir/first.so" --second "$temp_dir/second.so" --output "$output_dir/reproducibility.json"
  assert_json "$output_dir/reproducibility.json"
  printf 'different artifact\n' > "$temp_dir/second.so"
  if "$REPRODUCIBILITY_TOOL" --first "$temp_dir/first.so" --second "$temp_dir/second.so" --output "$output_dir/reproducibility-failure.json"; then
    fail '可重复构建验证必须拒绝不同哈希'
  fi

  if PKG_CONFIG_LIBDIR="$temp_dir/ohos-pkgconfig" "$CONTROLLED_BUILD" --source "$source_dir" --output "$output_dir/build" --skip-compile; then
    fail '受控构建必须拒绝缺少 libmpv.so 的来源目录'
  fi
}

main "$@"
