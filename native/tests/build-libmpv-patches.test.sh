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

main() {
  local work_dir build_sh ffmpeg_sh
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  work_dir="$temp_dir/libmpv-ohos-build"
  mkdir -p "$work_dir/scripts"
  git init -q "$work_dir"
  git -C "$work_dir" config user.email test@test.com
  git -C "$work_dir" config user.name Test
  write_original_build_sh "$work_dir/build.sh"
  write_original_ffmpeg_sh "$work_dir/scripts/ffmpeg.sh"
  write_original_mpv_sh "$work_dir/scripts/mpv.sh"
  git -C "$work_dir" add -A
  git -C "$work_dir" commit -qm initial

  # shellcheck disable=SC1090
  source "$BOOTSTRAP_SCRIPT"

  apply_build_script_patches "$work_dir" "$PATCHES_DIR"

  build_sh="$work_dir/build.sh"

  # 问题 A：libxml2 须在 ffmpeg 之前
  local ffmpeg_line libxml2_line
  ffmpeg_line=$(line_of_first_match 'ffmpeg.sh build' "$build_sh")
  libxml2_line=$(line_of_first_match 'libxml2.sh build' "$build_sh")
  [ -n "$ffmpeg_line" ] || fail "未找到 ffmpeg.sh 引用"
  [ -n "$libxml2_line" ] || fail "未找到 libxml2.sh 引用"
  [ "$libxml2_line" -lt "$ffmpeg_line" ] || \
    fail "libxml2.sh（行 $libxml2_line）应在 ffmpeg.sh（行 $ffmpeg_line）之前，dash demuxer 才能链接 libxml2"

  # 问题 B：harfbuzz 须在 freetype 之前
  local harfbuzz_line freetype_line
  harfbuzz_line=$(line_of_first_match 'harfbuzz.sh build' "$build_sh")
  freetype_line=$(line_of_first_match 'freetype.sh build' "$build_sh")
  [ -n "$harfbuzz_line" ] || fail "未找到 harfbuzz.sh 引用"
  [ -n "$freetype_line" ] || fail "未找到 freetype.sh 引用"
  [ "$harfbuzz_line" -lt "$freetype_line" ] || \
    fail "harfbuzz.sh（行 $harfbuzz_line）应在 freetype.sh（行 $freetype_line）之前，freetype 才能稳定链接 harfbuzz"

  # FFmpeg configure 显式启用 libxml2、DASH 与静态 libsmbclient。
  ffmpeg_sh="$work_dir/scripts/ffmpeg.sh"
  grep -q -- '--enable-libxml2' "$ffmpeg_sh" || fail "ffmpeg.sh 缺少 --enable-libxml2"
  grep -q -- '--enable-demuxer=dash' "$ffmpeg_sh" || fail "ffmpeg.sh 缺少 --enable-demuxer=dash"
  grep -q -- '--enable-gpl' "$ffmpeg_sh" || fail "ffmpeg.sh 缺少 --enable-gpl（libsmbclient 为 GPLv3）"
  grep -q -- '--enable-libsmbclient' "$ffmpeg_sh" || fail "ffmpeg.sh 缺少 --enable-libsmbclient"
  grep -q -- '--pkg-config-flags=--static' "$ffmpeg_sh" || fail "ffmpeg.sh 必须通过静态 pkg-config 解析 libsmbclient 传递依赖"

  # Direct SMB 凭据必须经 FFmpeg 协议选项回调提供，不能放入 URL 或 HTTP 请求头。
  local libsmbclient_source="$work_dir/libmpv/ffmpeg/libavformat/libsmbclient.c"
  mkdir -p "$(dirname "$libsmbclient_source")"
  cat > "$libsmbclient_source" <<'ORIGINAL_LIBSMBCLIENT_C'
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
typedef struct {
    const AVClass *class;
    SMBCCTX *ctx;
    int dh;
    int fd;
    int64_t filesize;
    int trunc;
    int timeout;
    char *workgroup;
} LIBSMBContext;

static void libsmbc_get_auth_data(SMBCCTX *c, const char *server, const char *share,
                                  char *workgroup, int workgroup_len,
                                  char *username, int username_len,
                                  char *password, int password_len)
{
    /* Do nothing yet. Credentials are passed via url.
     * Callback must exists, there might be a segmentation fault otherwise. */
}

static av_cold int libsmbc_connect(URLContext *h)
{
    LIBSMBContext *libsmbc = h->priv_data;

    libsmbc->ctx = smbc_new_context();
    if (!libsmbc->ctx) {
        int ret = AVERROR(errno);
        av_log(h, AV_LOG_ERROR, "Cannot create context: %s.\n", strerror(errno));
        return ret;
    }
    if (!smbc_init_context(libsmbc->ctx)) {
        int ret = AVERROR(errno);
        av_log(h, AV_LOG_ERROR, "Cannot initialize context: %s.\n", strerror(errno));
        return ret;
    }
    smbc_set_context(libsmbc->ctx);

    smbc_setOptionUserData(libsmbc->ctx, h);
    smbc_setFunctionAuthDataWithContext(libsmbc->ctx, libsmbc_get_auth_data);

    if (libsmbc->timeout != -1)
        smbc_setTimeout(libsmbc->ctx, libsmbc->timeout);
    if (libsmbc->workgroup)
        smbc_setWorkgroup(libsmbc->ctx, libsmbc->workgroup);

    if (smbc_init(NULL, 0) < 0) {
        int ret = AVERROR(errno);
        av_log(h, AV_LOG_ERROR, "Initialization failed: %s\n", strerror(errno));
        return ret;
    }
    return 0;
}

/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
/* fixture padding */
#define OFFSET(x) offsetof(LIBSMBContext, x)
#define D AV_OPT_FLAG_DECODING_PARAM
#define E AV_OPT_FLAG_ENCODING_PARAM
static const AVOption options[] = {
    {"timeout",   "set timeout in ms of socket I/O operations",    OFFSET(timeout), AV_OPT_TYPE_INT, {.i64 = -1}, -1, INT_MAX, D|E },
    {"truncate",  "truncate existing files on write",              OFFSET(trunc),   AV_OPT_TYPE_INT, { .i64 = 1 }, 0, 1, E },
    {"workgroup", "set the workgroup used for making connections", OFFSET(workgroup), AV_OPT_TYPE_STRING, { 0 }, 0, 0, D|E },
    {NULL}
};
ORIGINAL_LIBSMBCLIENT_C
  apply_ffmpeg_source_patches "$work_dir" "$FFMPEG_PATCHES_DIR"
  grep -q -- 'char \*username;' "$libsmbclient_source" || fail "libsmbclient 回调缺少会话用户名选项"
  grep -q -- 'char \*password;' "$libsmbclient_source" || fail "libsmbclient 回调缺少会话密码选项"
  grep -q -- 'smbc_setOptionUserData(libsmbc->ctx, libsmbc);' "$libsmbclient_source" || \
    fail "libsmbclient 必须将协议私有上下文交给认证回调"
  if grep -q -- 'smbc_setOptionUserData(libsmbc->ctx, h);' "$libsmbclient_source"; then
    fail "libsmbclient 不能将 URLContext 误作认证回调的协议私有上下文"
  fi
  grep -q -- 'av_strlcpy(username, libsmbc->username' "$libsmbclient_source" || fail "libsmbclient 回调未复制会话用户名"
  grep -q -- 'av_strlcpy(password, libsmbc->password' "$libsmbclient_source" || fail "libsmbclient 回调未复制会话密码"
  grep -q -- '"username", "set the username used for SMB authentication"' "$libsmbclient_source" || fail "libsmbclient 缺少用户名 AVOption"
  grep -q -- '"password", "set the password used for SMB authentication"' "$libsmbclient_source" || fail "libsmbclient 缺少密码 AVOption"

  # 问题 C：mpv.sh 的 meson setup 须带 --wipe，避免缓存命中时复用 stale .build
  # 导致 build.ninja 退化为只构建静态库（libmpv.a），mv libmpv.so 失败
  local mpv_sh="$work_dir/scripts/mpv.sh"
  grep -q -- '--wipe' "$mpv_sh" || fail "mpv.sh 缺少 --wipe（缓存命中时 meson 会复用 stale .build 配置）"
  grep -q -- '-Dgpl=true' "$mpv_sh" || fail "mpv.sh 缺少 -Dgpl=true"
  ! grep -q -- '-Dgpl=false' "$mpv_sh" || fail "mpv.sh 不应禁用 GPL 功能"

  # 幂等性：重复应用已应用补丁应跳过而非报错
  apply_build_script_patches "$work_dir" "$PATCHES_DIR" \
    || fail "重复应用补丁应跳过已应用项而非报错"

  # 补丁目录不存在时正常退出
  apply_build_script_patches "$work_dir" "$temp_dir/no-such-dir" \
    || fail "补丁目录不存在时应正常退出"
}

main "$@"
