#!/usr/bin/env bash
# 验证 native/patches/libmpv-ohos-build/*.patch 修正了 libmpv-ohos-build 的依赖顺序与 FFmpeg configure，
# 解决 issue #21：
#   - 问题 A：libxml2 必须在 ffmpeg 之前构建，且 ffmpeg.sh 显式 --enable-libxml2 --enable-demuxer=dash
#     （FFmpeg dash_demuxer_deps="libxml2"，缺 libxml2 则 dashdec.c 不编译）
#   - 问题 B：harfbuzz 必须在 freetype 之前构建，freetype 才能稳定检测并链接 harfbuzz shaping
#     （否则缓存命中时 freetype 启用 shaping 但链接未带入 libharfbuzz.a，间歇性失败）
#   - 问题 C：mpv.sh 的 meson setup 须带 --wipe，缓存命中时复用 stale .build 会让
#     build.ninja 退化为只构建静态库（libmpv.a），导致 mv libmpv.so 失败
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly BOOTSTRAP_SCRIPT="$PROJECT_ROOT/native/scripts/build-libmpv-bootstrap.sh"
readonly PATCH_FIXTURE_DIR="$SCRIPT_DIR/fixtures/libmpv-ohos-build"

# PATCHES_DIR 由 bootstrap 脚本定义（source 后可用），避免重复声明导致 readonly 冲突。

fail() {
  echo "测试失败：$*" >&2
  exit 1
}

# 来自 libmpv-ohos-build commit 1bab837e 的原始 build.sh。
# 若锁定 commit 更新导致补丁失效，此处需同步更新基线，测试会及时暴露。
write_original_build_sh() {
  cat > "$1" <<'ORIGINAL_BUILD_SH'
#!/bin/bash

set -eu

# ffmpeg
./scripts/mbedtls.sh build
./scripts/dav1d.sh build
./scripts/ffmpeg.sh build

# fontconfig
./scripts/libxml2.sh build

# libass
./scripts/fribidi.sh build
./scripts/freetype.sh build
./scripts/harfbuzz.sh build
./scripts/fontconfig.sh build
./scripts/libass.sh build

# libplacebo
./scripts/dovi_tools.sh build
./scripts/lcms.sh build
./scripts/shaderc.sh build
./scripts/libplacebo.sh build

# mpv
./scripts/lua.sh build
./scripts/mpv.sh build
ORIGINAL_BUILD_SH
}

write_original_ffmpeg_sh() {
  cat > "$1" <<'ORIGINAL_FFMPEG_SH'
#!/bin/bash

set -eu

ROOT_DIR=$(cd $(dirname "$0")/..; pwd)

. $ROOT_DIR/env.sh

pushd $ROOT_DIR/libmpv/ffmpeg

if [ "$1" == "build" ]; then
	echo -e "\nBuilding FFmpeg..."
elif [ "$1" == "clean" ]; then
	rm -rf .build
	exit 0
else
	exit 1
fi

mkdir -p .build
cd .build

../configure \
  --prefix=$DEST \
  --arch=aarch64 \
  --cpu=armv8-a \
  --target-os=linux \
  --enable-static \
  --disable-shared \
  --enable-version3 \
  --enable-pic \
  --disable-doc \
  --disable-programs \
  \
  --enable-cross-compile \
  --cc="$CC" \
  --extra-cflags="-I$DEST/include" \
  --extra-ldflags="-L$DEST/lib" \
  --enable-libdav1d \
  --enable-mbedtls \
  --disable-vulkan \
  \
  --disable-devices \
  --disable-avdevice \
  --disable-muxers \
  --disable-encoders \
  --enable-ohcodec \
  --enable-encoder=png,mjpeg
make -j$CORES
make install

popd
ORIGINAL_FFMPEG_SH
}

# 来自 libmpv-ohos-build commit 1bab837e 的原始 mpv.sh。
# 补丁 0004 在 meson setup 加 --wipe，强制每次重新 configure，避免缓存命中时复用 stale .build。
write_original_mpv_sh() {
cat > "$1" <<'ORIGINAL_MPV_SH'
#!/bin/bash

set -eu

ROOT_DIR=$(cd $(dirname "$0")/..; pwd)

. $ROOT_DIR/env.sh

pushd $ROOT_DIR/libmpv/mpv

if [ "$1" == "build" ]; then
	echo -e "\nBuilding mpv..."
elif [ "$1" == "clean" ]; then
	rm -rf .build
	exit 0
else
	exit 1
fi

mkdir -p .build
cd .build

meson setup .. \
  --cross-file $ROOT_DIR/libmpv/arm64-crossfile.ini \
  --prefix=$DEST/mpv \
  --default-library shared \
  --strip \
  -Dopensles=disabled \
  -Dohos=enabled \
  -Degl-ohos=enabled \
  -Dvulkan=enabled \
  -Dshaderc=enabled \
  -Dlua=enabled \
  -Dgpl=false \
  -Dbuild-date=false \
  -Dcplayer=false \
  -Dmanpage-build=disabled
ninja -j$CORES
ninja install

cd $DEST/mpv/lib
mv libmpv.so ../../libmpv.so

popd
ORIGINAL_MPV_SH
}

line_of_first_match() {
  grep -n -- "$1" "$2" | head -1 | cut -d: -f1
}

copy_pinned_patch_fixture() {
  local output_root="$1"
  [ -d "$PATCH_FIXTURE_DIR" ] || fail "缺少独立维护的锁定 mpv patch fixture"
  cp -R "$PATCH_FIXTURE_DIR"/. "$output_root"/
}

main() {
  local work_dir build_sh ffmpeg_sh
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  # shellcheck disable=SC1090
  source "$BOOTSTRAP_SCRIPT"

  work_dir="$temp_dir/libmpv-ohos-build"
  mkdir -p "$work_dir/scripts"
  copy_pinned_patch_fixture "$work_dir"
  git init -q "$work_dir"
  git -C "$work_dir" config user.email test@test.com
  git -C "$work_dir" config user.name Test
  write_original_build_sh "$work_dir/build.sh"
  write_original_ffmpeg_sh "$work_dir/scripts/ffmpeg.sh"
  write_original_mpv_sh "$work_dir/scripts/mpv.sh"
  git -C "$work_dir" add -A
  git -C "$work_dir" commit -qm initial

  apply_build_script_patches "$work_dir" "$PATCHES_DIR"

  build_sh="$work_dir/build.sh"

  # external shared FFmpeg 由 bootstrap staging，上游不得再次构建静态 FFmpeg。
  ! grep -q -- 'ffmpeg.sh build' "$build_sh" || fail "build.sh 不得构建内嵌 FFmpeg"
  ! grep -q -- 'mbedtls.sh build' "$build_sh" || fail "build.sh 不得为内嵌 FFmpeg构建 mbedTLS"
  ! grep -q -- 'dav1d.sh build' "$build_sh" || fail "build.sh 不得为内嵌 FFmpeg 构建 dav1d"

  # 问题 B：harfbuzz 须在 freetype 之前
  local harfbuzz_line freetype_line
  harfbuzz_line=$(line_of_first_match 'harfbuzz.sh build' "$build_sh")
  freetype_line=$(line_of_first_match 'freetype.sh build' "$build_sh")
  [ -n "$harfbuzz_line" ] || fail "未找到 harfbuzz.sh 引用"
  [ -n "$freetype_line" ] || fail "未找到 freetype.sh 引用"
  [ "$harfbuzz_line" -lt "$freetype_line" ] || \
    fail "harfbuzz.sh（行 $harfbuzz_line）应在 freetype.sh（行 $freetype_line）之前，freetype 才能稳定链接 harfbuzz"

  # ffmpeg.sh 保留为上游源码，但主流程不可调用，避免 libmpv 静态内嵌 FFmpeg。
  ffmpeg_sh="$work_dir/scripts/ffmpeg.sh"
  grep -q -- '--enable-static' "$ffmpeg_sh" || fail "fixture 应保留上游静态 FFmpeg 脚本，以证明 build.sh 已绕过它"

  # SMB 凭据补丁由 external FFmpeg producer 应用并在 VERSION 中声明。
  ! grep -q -- 'apply_ffmpeg_source_patches' "$build_sh" || fail "上游 build.sh 不得修改 external FFmpeg"

  # 问题 C：mpv.sh 的 meson setup 须带 --wipe，避免缓存命中时复用 stale .build
  # 导致 build.ninja 退化为只构建静态库（libmpv.a），mv libmpv.so 失败
  local mpv_sh="$work_dir/scripts/mpv.sh"
  grep -q -- '--wipe' "$mpv_sh" || fail "mpv.sh 缺少 --wipe（缓存命中时 meson 会复用 stale .build 配置）"
  grep -q -- '-Dgpl=true' "$mpv_sh" || fail "mpv.sh 缺少 -Dgpl=true"
  grep -q -- 'VIDALL_PLAYER_FFMPEG_STAGING/lib/pkgconfig' "$mpv_sh" || fail "mpv.sh 未使用 external FFmpeg pkg-config"
  grep -q -- 'PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"' "$mpv_sh" || fail "mpv.sh 未隔离 pkg-config 搜索路径"
  ! grep -q -- '-Dgpl=false' "$mpv_sh" || fail "mpv.sh 不应禁用 GPL 功能"

  # 宿主 FFmpeg 8 不提供 mpv-ohos 私有零拷贝 ABI，必须禁用对应 surface driver。
  grep -q -- 'video/out/ohos_common.c' "$work_dir/libmpv/mpv/meson.build" || fail "应保留 OHOS 窗口支持"
  ! grep -q -- "'video/out/hwdec/hwdec_ohcodec.c'" "$work_dir/libmpv/mpv/meson.build" || fail "不得编译私有 OHCodec hwdec driver"
  ! grep -q -- "'video/out/hwdec/hwdec_ohcodec_gl.c'" "$work_dir/libmpv/mpv/meson.build" || fail "不得编译私有 OHCodec GL interop"
  ! grep -q -- "'video/out/hwdec/hwdec_ohcodec_pl.c'" "$work_dir/libmpv/mpv/meson.build" || fail "不得编译私有 OHCodec Vulkan interop"
  ! grep -q -- 'ra_hwdec_ohcodec' "$work_dir/libmpv/mpv/video/out/gpu/hwdec.c" || fail "不得注册私有 OHCodec surface driver"

  # 幂等性：重复应用已应用补丁应跳过而非报错
  apply_build_script_patches "$work_dir" "$PATCHES_DIR" \
    || fail "重复应用补丁应跳过已应用项而非报错"

  # 补丁目录不存在时正常退出
  apply_build_script_patches "$work_dir" "$temp_dir/no-such-dir" \
    || fail "补丁目录不存在时应正常退出"
}

main "$@"
