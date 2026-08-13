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
  cat > "$mock_bin/llvm-readelf" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -h) printf '  Machine:                           AArch64\n' ;;
  -d) printf ' 0x0000000000000001 (NEEDED)             Shared library: [libc++.so]\n' ;;
esac
EOF
  chmod +x "$mock_bin/llvm-readelf"
  cat > "$mock_bin/llvm-nm" <<'EOF'
#!/usr/bin/env bash
python3 -c 'print("\n".join(f"00000000 T symbol_{i:07d}" for i in range(300000)))'
EOF
  chmod +x "$mock_bin/llvm-nm"
  : > "$temp_dir/mock-libmpv.so"
  OHOS_NDK='' OHOS_NDK_HOME='' PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-large.json" --allow libc++.so
  assert_json "$output_dir/elf-audit-large.json"
  python3 - "$output_dir/elf-audit-large.json" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
assert report['status'] == 'passed'
assert len(report['exportedDynamicSymbols']) == 300000
PY

  if OHOS_NDK='' OHOS_NDK_HOME='' PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-require-only.json" --require libc++.so; then
    fail '仅指定 --require 时未允许的动态依赖必须失败'
  fi
  python3 - "$output_dir/elf-audit-require-only.json" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
assert report['requiredLibraries'] == ['libc++.so']
assert report['missingRequiredLibraries'] == []
assert report['forbiddenLibraries'] == []
PY

  cat > "$mock_bin/llvm-readelf" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -h) printf '  Machine:                           AArch64\n' ;;
  -d) printf ' 0x0000000000000001 (NEEDED)             Shared library: [libsmbclient.so]\n' ;;
esac
EOF
  chmod +x "$mock_bin/llvm-readelf"
  cat > "$mock_bin/llvm-nm" <<'EOF'
#!/usr/bin/env bash
printf '00000000 T fixture_symbol\n'
EOF
  chmod +x "$mock_bin/llvm-nm"
  if OHOS_NDK='' OHOS_NDK_HOME='' PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-forbidden.json" --allow libsmbclient.so --forbid libsmbclient.so; then
    fail 'ELF 审计必须拒绝动态链接的 libsmbclient.so'
  fi
  if OHOS_NDK='' OHOS_NDK_HOME='' PATH="$mock_bin:$PATH" "$ELF_AUDIT_TOOL" --input "$temp_dir/mock-libmpv.so" --output "$output_dir/elf-audit-forbid-only.json" --forbid libsmbclient.so; then
    fail '仅指定 --forbid 时也必须拒绝动态链接的 libsmbclient.so'
  fi
  python3 - "$output_dir/elf-audit-forbidden.json" "$output_dir/elf-audit-forbid-only.json" <<'PY'
import json
import sys
for path in sys.argv[1:]:
    report = json.load(open(path, encoding='utf-8'))
    assert report['status'] == 'failed'
    assert report['forbiddenLibraries'] == ['libsmbclient.so']
    assert report['forbiddenNeededLibraries'] == ['libsmbclient.so']
PY

  grep -Fq 'sbom.cdx.json' "$CONTROLLED_BUILD" || fail '受控构建必须使用统一的 CycloneDX SBOM 文件名'
  grep -Fq -- '--allow libEGL.so --allow libvulkan.so --allow libohaudio.so' "$CONTROLLED_BUILD" || fail '受控构建必须允许 MPV 的 OpenHarmony 图形和音频系统依赖'
  grep -Fq -- '--allow libnative_buffer.so --allow libnative_image.so --allow libnative_window.so' "$CONTROLLED_BUILD" || fail '受控构建必须允许 MPV 的 OpenHarmony native window 系统依赖'
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
  grep -Fq -- 'prepare_ffmpeg_shared_prefix' "$PROJECT_ROOT/native/scripts/build-libmpv-bootstrap.sh" || fail 'bootstrap 必须校验 external FFmpeg prefix'
  grep -Fq -- '--enable-libsmbclient' "$PROJECT_ROOT/native/scripts/build-libmpv-bootstrap.sh" || fail 'external FFmpeg 门禁必须要求 libsmbclient'
  grep -Fq -- '--enable-shared' "$PROJECT_ROOT/native/scripts/build-libmpv-bootstrap.sh" || fail 'external FFmpeg 门禁必须要求 shared libraries'
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
detection_job = workflow.split('  detect-build-changes:', 1)[1].split('  build-libmpv-external-ffmpeg:', 1)[0]
for build_input in (
    'native/scripts/build-libmpv-bootstrap.sh',
    'native/scripts/audit-libmpv-elf.sh',
    'native/patches/libmpv-ohos-build',
    'native/config/sources.lock.json',
):
    assert build_input in detection_job, f'CI 变更检测必须覆盖动态 libmpv 输入：{build_input}'
assert 'native/scripts/build-libsmbclient-controlled.sh' not in detection_job, 'CI 变更检测不得继续跟踪旧 libsmbclient 构建脚本'
assert 'force_build' in workflow, 'CI 必须支持强制重建入口'
assert 'ffmpeg_artifact_repository:' in workflow, 'CI 必须声明受控 FFmpeg producer 仓库输入'
assert 'ffmpeg_artifact_run_id:' in workflow, 'CI 必须使用固定 workflow run ID 获取 FFmpeg 制品'
assert 'build-libmpv-external-ffmpeg:' in workflow, 'CI 必须执行 external FFmpeg libmpv 构建'
libmpv_job = workflow.split('  build-libmpv-external-ffmpeg:', 1)[1].split('  controlled-release:', 1)[0]
assert 'FFMPEG_ARTIFACT_RUN_ID:' in libmpv_job and "'31637632656'" in libmpv_job, 'CI 必须为自动事件提供固定 FFmpeg run ID'
assert 'gh run download "$FFMPEG_ARTIFACT_RUN_ID"' in libmpv_job, 'CI 必须通过环境变量安全传递固定 run ID'
assert '--repo "$FFMPEG_ARTIFACT_REPOSITORY"' in libmpv_job, 'CI 必须通过环境变量安全传递 producer 仓库'
assert '${{ inputs.ffmpeg_artifact_run_id }}' not in libmpv_job.split('run: |', 1)[1], 'workflow inputs 不得直接插值进 shell'
assert '--name ffmpeg-8.0-ohos-arm64-v8a' in libmpv_job, 'CI 必须下载受控 ARM64 FFmpeg 8 制品'
assert 'VIDALL_PLAYER_FFMPEG_PREFIX:' in libmpv_job, 'CI 必须向 bootstrap 注入 external FFmpeg prefix'
assert 'build-libmpv-bootstrap.sh' in libmpv_job, 'external FFmpeg job 必须执行受控引导脚本'
assert 'test -n "${OHOS_NDK:-}"' in libmpv_job, '真实 libmpv 构建必须验证 OpenHarmony NDK'
assert '/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony' in libmpv_job, 'CI 必须兼容自动发现 DevEco Studio 默认 OpenHarmony NDK'
assert 'echo "OHOS_NDK=$OHOS_NDK" >> "$GITHUB_ENV"' in libmpv_job, 'CI 必须向后续步骤导出自动发现的 OpenHarmony NDK'
assert 'llvm-readelf' in libmpv_job and 'clang' in libmpv_job, 'CI 必须验证 OpenHarmony NDK 编译与审计工具'
assert 'RUST_TOOLCHAIN: 1.85.1' in libmpv_job, 'CI 必须固定 libmpv 构建使用的 Rust 工具链'
assert 'CARGO_C_VERSION: 0.10.13' in libmpv_job, 'CI 必须固定与 Rust 1.85 兼容的 cargo-c 版本'
assert 'command -v cargo-cbuild' in libmpv_job, 'CI 必须通过 cargo-c 实际安装的 cargo-cbuild 可执行文件验证固定版本'
assert 'command -v cargo-c ' not in libmpv_job, 'CI 不得检查 cargo-c 不会安装的同名可执行文件'
assert 'RUSTUP_VERSION: 1.28.2' in libmpv_job, 'CI 必须固定 rustup 安装器版本'
assert 'static.rust-lang.org/rustup/archive/$RUSTUP_VERSION' in libmpv_job, 'CI 必须从固定 rustup archive 获取安装器'
assert 'shasum -a 256 -c' in libmpv_job and 'rustup default "$RUST_TOOLCHAIN"' in libmpv_job, 'CI 必须校验 rustup 安装器并始终选择固定工具链'
assert 'https://sh.rustup.rs' not in libmpv_job, 'CI 不得执行未固定内容的 rustup 在线安装脚本'
assert 'cat > "$TOOL_DIR/wget"' in libmpv_job and 'echo "$TOOL_DIR" >> "$GITHUB_PATH"' in libmpv_job, 'CI 必须为上游提供受限 wget 兼容工具'
assert 'elf-audit.json' in libmpv_job, 'CI 必须验证 ELF 审计报告'
assert "assert not report['sizeExceeded']" in libmpv_job, 'CI 必须验证 libmpv 体积预算'
assert 'GPL-3.0-or-later.txt' in libmpv_job, 'CI 必须验证 FFmpeg GPL 许可证材料'
assert 'ffmpeg-runtime-arm64' in libmpv_job, 'CI 必须独立上传供最终宿主 HAP 使用的 FFmpeg runtime'
assert 'VIDALL_PLAYER_SMB_SYSROOT' not in workflow, 'CI 不得继续向 libmpv 注入旧 SMB sysroot'
assert 'build-libsmbclient:' not in workflow, 'CI 不得在 libmpv 流程中重复构建 libsmbclient'
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
