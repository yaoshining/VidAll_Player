#!/usr/bin/env bash
# 受控交叉构建 libsmbclient (Samba 4.20.7) → OpenHarmony aarch64-linux-ohos 静态库。
#
# 本脚本在预装 DevEco Studio (OpenHarmony NDK) 的 macOS (arm64/x64) 宿主上执行，
# 产出仅包含 SMB 协议所需的 libsmbclient.a / libsmbclient.h / smbclient.pc，
# 供 FFmpeg --enable-libsmbclient 静态链接进 libmpv.so。
#
# 传递依赖闭包（全部静态）：
#   zlib → popt → gmp → nettle → libtasn1 → gnutls → samba/libsmbclient
#
# 关键技术点：
#   - OHOS sysroot 基于 musl，必须向 configure 风格构建传递 __MUSL__=1。
#   - GNU config.sub 不识别 linux-ohos；Samba 使用 --host=aarch64-linux-musl，
#     交叉语义由 CC 中的 --target=aarch64-linux-ohos --sysroot=... 承载。
#   - Samba 4.20.7 的 use_hostcc 路径在真实交叉编译下不完整：host 工具
#     (compile_et/asn1_compile) 会引入交叉 config.h，导致 Linux 专有头泄漏。
#     规避方案：在独立源码树用原生 configure 预编译这两个 host 工具，再通过
#     USING_SYSTEM_COMPILE_ET / USING_SYSTEM_ASN1_COMPILE 让交叉构建复用之，
#     并以 SAMBA_SKIP_HOSTCC 跳过所有 hostcc 子系统。
#   - 交叉回答 (cross-answers) 覆盖所有运行期探测；以 rsplit 解析含冒号的回答。
set -euo pipefail

# ---------------- 可配置入口 ----------------
: "${OHOS_NDK:=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony}"
: "${WORK_DIR:=$HOME/.cache/vidall-player/smb-src}"
: "${PREFIX:=$HOME/.cache/vidall-player/smb-sysroot}"
: "${SAMBA_TAG:=samba-4.20.7}"
: "${SAMBA_COMMIT:=3984b04d7085c428ab3126ef4cfac2a396b5b29e}"
: "${JOBS:=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

TARGET=aarch64-linux-ohos
HOST_TRIPLET=aarch64-linux-musl
SYSROOT="$OHOS_NDK/native/sysroot"
TOOLCHAIN="$OHOS_NDK/native/llvm/bin"
WRAPPER_DIR="$WORK_DIR/wrappers"
SAMBA_DIR="$WORK_DIR/samba"
SAMBA_HOST_DIR="$WORK_DIR/samba-host"

log() { printf '\033[1;34m[smb]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[smb] 错误：%s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$OHOS_NDK" ] || die "OHOS_NDK 不存在：$OHOS_NDK（请在预装 DevEco Studio 的 runner 上运行）"
[ -x "$TOOLCHAIN/clang" ] || die "未找到交叉 clang：$TOOLCHAIN/clang"
command -v pkg-config >/dev/null || die "缺少 pkg-config"
command -v python3 >/dev/null || die "缺少 python3"
command -v yacc >/dev/null 2>&1 || command -v bison >/dev/null 2>&1 || die "缺少 yacc/bison（brew install bison）"
command -v flex >/dev/null || die "缺少 flex（brew install flex）"
command -v autopoint >/dev/null 2>&1 || log "警告: autopoint 不可用, popt 构建将使用 release 预生成文件"
command -v glibtoolize >/dev/null 2>&1 || command -v libtoolize >/dev/null || die "缺少 libtool（brew install libtool）"

mkdir -p "$PREFIX/lib/pkgconfig" "$PREFIX/include" "$WORK_DIR" "$WRAPPER_DIR"

# self-hosted runner 上 WORK_DIR 会跨 CI 运行残留, 旧源码可能被之前的
# glibtoolize/autoreconf 损坏。缓存未命中需要真实构建时, 先清理所有依赖
# 源码目录, 确保从干净 tarball 重新解压 (Samba git 仓库单独保留以加速 clone)。
clean_src() {
  log "清理残留依赖源码目录..."
  for d in "$WORK_DIR"/zlib-* "$WORK_DIR"/popt-* "$WORK_DIR"/gmp-*            "$WORK_DIR"/nettle-* "$WORK_DIR"/libtasn1-* "$WORK_DIR"/gnutls-*            "$WORK_DIR"/gnutls-stubs; do
    [ -e "$d" ] && rm -rf "$d" || true
  done
}

# ---------------- 现代 bison（macOS 12 系统 bison 2.3 过旧） ----------------
build_modern_bison() {
  if bison --version | head -1 | grep -qE "GNU Bison [3-9]"; then
    log "检测到现代 bison: $(bison --version | head -1)"
    return 0
  fi
  log "构建 bison 3.8.2 (替换过旧系统版本)"
  local d="$WORK_DIR/bison-3.8.2"
  if [ ! -d "$d" ]; then
    fetch_extract https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.gz bison-3.8.2 || return 1
  fi
  ( cd "$d" && ./configure --prefix="$PREFIX" --disable-doc     && make -j"$JOBS" && make install ) || return 1
  export PATH="$PREFIX/bin:$PATH"
  log "已安装 bison: $($PREFIX/bin/bison --version | head -1)"
}

# ---------------- 交叉环境 ----------------
setup_cross_env() {
  export OHOS_NDK SYSROOT TOOLCHAIN TARGET PREFIX WRAPPER_DIR
  export PATH="$WRAPPER_DIR:$TOOLCHAIN:$PATH"
  export CC="$TOOLCHAIN/clang --target=$TARGET --sysroot=$SYSROOT"
  export CXX="$TOOLCHAIN/clang++ --target=$TARGET --sysroot=$SYSROOT"
  export AR="$TOOLCHAIN/llvm-ar"
  export RANLIB="$TOOLCHAIN/llvm-ranlib"
  export STRIP="$TOOLCHAIN/llvm-strip"
  export NM="$TOOLCHAIN/llvm-nm"
  export LD="$TOOLCHAIN/ld.lld"
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
  export PKG_CONFIG_LIBDIR="$SYSROOT/usr/lib"
  export PKG_CONFIG_SYSROOT_DIR="$SYSROOT"
  # This explicit marker reaches the incorrectly scheduled HostCC tasks too.
  export CFLAGS="-fPIC -D__MUSL__=1 -DSAMBA_OHOS_CROSS=1 -I$PREFIX/include"
  export CXXFLAGS="-fPIC -D__MUSL__=1 -DSAMBA_OHOS_CROSS=1 -I$PREFIX/include"
  export LDFLAGS="-L$PREFIX/lib"
  # waf find_program('clang') 会优先命中这些包装器，确保交叉语义不被宿主 clang 覆盖。
  for w in clang clang++ cc c++; do
    local real=$w
    [ "$w" = cc ] && real=clang
    [ "$w" = c++ ] && real=clang++
    cat > "$WRAPPER_DIR/$w" <<EOF
#!/usr/bin/env bash
exec "$TOOLCHAIN/$real" --target="$TARGET" --sysroot="$SYSROOT" "\$@"
EOF
    chmod +x "$WRAPPER_DIR/$w"
  done
  # Samba waf 内部硬编码调用 python, macOS 12 runner 不提供 /usr/bin/python,
  # 提供一个指向 python3 的 symlink 以满足 waf 需要。
}

# ---------------- 源码检出 ----------------
# GitLab 偶发 503, 重试最多 5 次, 每次间隔递增。
git_clone_retry() {
  local url="$1" dest="$2" attempt=0 max=5
  while [ "$attempt" -lt "$max" ]; do
    attempt=$((attempt + 1))
    log "git clone 尝试 $attempt/$max: $url"
    if git clone "$url" "$dest"; then
      return 0
    fi
    rm -rf "$dest"
    [ "$attempt" -lt "$max" ] || { log "git clone 在 $max 次尝试后仍失败: $url"; return 1; }
    local wait=$((attempt * 15))
    log "等待 ${wait}s 后重试..."
    sleep "$wait"
  done
}

fetch_samba() {
  if [ ! -d "$SAMBA_DIR/.git" ]; then
    log "克隆 Samba $SAMBA_TAG ..."
    git_clone_retry https://gitlab.com/samba-team/samba.git "$SAMBA_DIR"
  fi
  ( cd "$SAMBA_DIR" && git checkout "$SAMBA_COMMIT" && git reset --hard "$SAMBA_COMMIT" && git clean -fd )
}

# ---------------- 依赖链构建 ----------------
# 下载到临时文件, 校验 tar 包未截断后才解压, 减少 iMac runner 网络抽风导致的失败。
# 用法: fetch_extract <url> <label>
fetch_extract() {
  local url="$1" label="$2"
  local attempt=0 max=4
  while [ "$attempt" -lt "$max" ]; do
    attempt=$((attempt + 1))
    log "$label 下载 尝试 $attempt/$max: $url"
    local tmp="$WORK_DIR/${label}.$$"
    if curl -fsSL --retry 3 --retry-delay 5 "$url" -o "$tmp"; then
      case "$url" in
        *.tar.xz|*.txz) tar tJf "$tmp" >/dev/null 2>&1 && tar xJf "$tmp" -C "$WORK_DIR" && rm -f "$tmp" && return 0 ;;
        *.tar.gz|*.tgz) tar tzf "$tmp" >/dev/null 2>&1 && tar xzf "$tmp" -C "$WORK_DIR" && rm -f "$tmp" && return 0 ;;
        *) log "未识别的压缩格式: $url"; rm -f "$tmp"; return 1 ;;
      esac
    fi
    rm -f "$tmp"
    [ "$attempt" -lt "$max" ] || { log "$label 下载在 $max 次尝试后仍失败"; return 1; }
    sleep $((attempt * 10))
  done
}

build_zlib() {
  log "构建 zlib 1.3.1"
  local d="$WORK_DIR/zlib-1.3.1"
  if [ ! -d "$d" ]; then
    fetch_extract https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz zlib-1.3.1 || return 1
  fi
  ( cd "$d" && ./configure --static --prefix="$PREFIX" \
    && make AR="$AR" ARFLAGS="rcs" RANLIB="$RANLIB" -j"$JOBS" \
    && make AR="$AR" ARFLAGS="rcs" RANLIB="$RANLIB" install )
}

build_popt() {
  log "构建 popt 1.19"
  local d="$WORK_DIR/popt-1.19"
  if [ ! -d "$d" ]; then
    fetch_extract https://ftp.osuosl.org/pub/rpm/popt/releases/popt-1.x/popt-1.19.tar.gz popt-1.19 || return 1
  fi
  ( cd "$d"
    # release tarball 已含预生成 configure/build-aux, 不再运行 autopoint/glibtoolize
    # (glibtoolize --force 会覆盖 build-aux/compile 和 missing 导致 configure 失败)。
    ./configure --host="$HOST_TRIPLET" --prefix="$PREFIX" --enable-static --disable-shared
    make -j"$JOBS" && make install )
}

build_gmp() {
  log "构建 gmp 6.3.0"
  local d="$WORK_DIR/gmp-6.3.0"
  if [ ! -d "$d" ]; then
    fetch_extract https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz gmp-6.3.0 || return 1
  fi
  ( cd "$d"
    ./configure --host="$HOST_TRIPLET" --prefix="$PREFIX" --enable-static --disable-shared --with-pic
    make -j"$JOBS" && make install )
}

build_nettle() {
  log "构建 nettle 3.9.1"
  local d="$WORK_DIR/nettle-3.9.1"
  if [ ! -d "$d" ]; then
    fetch_extract https://ftp.gnu.org/gnu/nettle/nettle-3.9.1.tar.gz nettle-3.9.1 || return 1
  fi
  ( cd "$d"
    ./configure --host="$HOST_TRIPLET" --prefix="$PREFIX" --enable-static --disable-shared \
      --disable-documentation --disable-openssl
    make -j"$JOBS" && make install )
}

build_libtasn1() {
  log "构建 libtasn1 4.19.0"
  local d="$WORK_DIR/libtasn1-4.19.0"
  if [ ! -d "$d" ]; then
    fetch_extract https://ftp.gnu.org/gnu/libtasn1/libtasn1-4.19.0.tar.gz libtasn1-4.19.0 || return 1
  fi
  ( cd "$d"
    ./configure --host="$HOST_TRIPLET" --prefix="$PREFIX" --enable-static --disable-shared --with-pic
    make -j"$JOBS" && make install )
}

build_gnutls() {
  log "构建 gnutls 3.8.7"
  local d="$WORK_DIR/gnutls-3.8.7"
  if [ ! -d "$d" ]; then
    fetch_extract https://www.gnupg.org/ftp/gcrypt/gnutls/v3.8/gnutls-3.8.7.tar.xz gnutls-3.8.7 || return 1
  fi
  # gnutls 的 dlwrap 在未启用 zstd/brotli 时仍包含其头，需提供空桩。
  local stub="$WORK_DIR/gnutls-stubs"; mkdir -p "$stub" "$stub/brotli"
  : > "$stub/zstd.h"; : > "$stub/brotli/encode.h"; : > "$stub/brotli/decode.h"; : > "$stub/brotli/common.h"
  # --with-included-unistring 后 gnutls 自带 gnulib 提供 error.h/error.c, 无需手动桩
  ( cd "$d"
    ./configure --host="$HOST_TRIPLET" --prefix="$PREFIX" --enable-static --disable-shared --with-pic \
      --disable-doc --disable-tests --disable-tools --disable-cxx --disable-maintainer-mode \
      --disable-openssl --disable-padlock --disable-guile --disable-hardware-acceleration \
      --without-p11-kit --without-idn --without-tpm --disable-nls --with-included-unistring \
      GMP_CFLAGS="-I$PREFIX/include" GMP_LIBS="-L$PREFIX/lib -lgmp" \
      NETTLE_CFLAGS="-I$PREFIX/include" NETTLE_LIBS="-L$PREFIX/lib -lnettle" \
      HOGWEED_CFLAGS="-I$PREFIX/include" HOGWEED_LIBS="-L$PREFIX/lib -lhogweed -lnettle" \
      LIBTASN1_CFLAGS="-I$PREFIX/include" LIBTASN1_LIBS="-L$PREFIX/lib -ltasn1" \
      CPPFLAGS="-I$stub -I$PREFIX/include"
    make -j"$JOBS" && make install )
}

build_dependencies() {
  build_zlib
  build_popt
  build_gmp
  build_nettle
  build_libtasn1
  build_gnutls
}

# ---------------- Samba 源补丁 ----------------
patch_samba_source() {
  log "应用 Samba 交叉编译补丁"
  cd "$SAMBA_DIR"

  # 补丁 1：交叉编译时跳过 -framework CoreFoundation（ld.lld 不识别 -framework）。
  python3 - <<'PY'
p='wscript'
s=open(p).read()
old="if sys.platform == 'darwin':"
new="if sys.platform == 'darwin' and not conf.env['CROSS_COMPILE']:"
assert old in s
open(p,'w').write(s.replace(old,new,1))
PY

  # 补丁 2：交叉回答解析对含冒号的回答使用 rsplit。
  python3 - <<'PY'
p='buildtools/wafsamba/samba_cross.py'
s=open(p).read()
s=s.replace("a = line.split(':', 1)","a = line.rsplit(':', 1)")
open(p,'w').write(s)
PY

  # 补丁 3：hostcc 钩子——在 process_source 创建任务后，为 use_hostcc 任务切到 HOSTCC。
  #   实际跨构建中 hostcc 子系统会被 SAMBA_SKIP_HOSTCC 跳过；此钩子保留作为兜底。
  cat >> buildtools/wafsamba/samba_waf18.py <<'PYEOF'

from waflib.TaskGen import feature, after_method

@feature('c', 'cxx')
@after_method('process_source', 'apply_link', 'propagate_uselib_vars', 'process_use', 'apply_uselib_local')
def samba_apply_hostcc(self):
    if not getattr(self, 'samba_use_hostcc', False):
        return
    bld = self.bld
    hostcc = bld.env.HOSTCC
    if not hostcc:
        return
    for tsk in getattr(self, 'tasks', []):
        tenv = tsk.env.derive()
        tenv.CC = hostcc
        tenv.CXX = hostcc + '++' if isinstance(hostcc, str) else list(hostcc)
        tenv.LINK_CC = hostcc
        tenv.LINK_CXX = hostcc
        tenv.AR = 'ar'
        tenv.ARFLAGS = ['rcs']
        tenv.CFLAGS = [f for f in (tsk.env.CFLAGS or []) if '--target' not in f and '--sysroot' not in f and '__MUSL__' not in f]
        tenv.CXXFLAGS = [f for f in (tsk.env.CXXFLAGS or []) if '--target' not in f and '--sysroot' not in f and '__MUSL__' not in f]
        tenv.LINKFLAGS = [f for f in (tsk.env.LINKFLAGS or []) if '--target' not in f and '--sysroot' not in f and '-framework' not in f]
        tsk.env = tenv
PYEOF

  # 补丁 4：交叉编译时不编译 charset_macosxfs.c（依赖 CoreFoundation）。
  python3 - <<'PY'
p='lib/util/charset/wscript_build'
s=open(p).read()
old="""bld.SAMBA_SUBSYSTEM('ICONV_WRAPPER',
                    source='''
                    iconv.c
                    weird.c
                    charset_macosxfs.c
                    ''',
                    public_deps='iconv replace talloc ' +  bld.env['icu-libs'])"""
new="""_iconv_src = '''
                    iconv.c
                    weird.c
                    '''
if not bld.env['CROSS_COMPILE']:
    _iconv_src += '                    charset_macosxfs.c\\n                    '
bld.SAMBA_SUBSYSTEM('ICONV_WRAPPER',
                    source=_iconv_src,
                    public_deps='iconv replace talloc ' +  bld.env['icu-libs'])"""
assert old in s
open(p,'w').write(s.replace(old,new))
PY

  # 补丁 5：使用系统 host 工具时仍设置 bld.env.COMPILE_ET / ASN1_COMPILE。
  python3 - <<'PY'
p='third_party/heimdal_build/wscript_build'
s=open(p).read()
s=s.replace(
"    bld.env['ASN1_COMPILE'] = os.path.join(bld.bldnode.parent.abspath(), 'asn1_compile')\n\n\nif not bld.CONFIG_SET('USING_SYSTEM_COMPILE_ET'):",
"    bld.env['ASN1_COMPILE'] = os.path.join(bld.bldnode.parent.abspath(), 'asn1_compile')\nelse:\n    bld.env['ASN1_COMPILE'] = os.path.join(bld.bldnode.parent.abspath(), 'asn1_compile')\n\n\nif not bld.CONFIG_SET('USING_SYSTEM_COMPILE_ET'):")
s=s.replace(
"    bld.env['COMPILE_ET'] = os.path.join(bld.bldnode.parent.abspath(), 'compile_et')\n",
"    bld.env['COMPILE_ET'] = os.path.join(bld.bldnode.parent.abspath(), 'compile_et')\nelse:\n    bld.env['COMPILE_ET'] = os.path.join(bld.bldnode.parent.abspath(), 'compile_et')\n")
open(p,'w').write(s)
PY

  # 补丁 6：SAMBA_SKIP_HOSTCC 时跳过所有 hostcc 子系统。
  python3 - <<'PY'
p='lib/replace/wscript'
s=open(p).read()
old="""    bld.SAMBA_SUBSYSTEM('LIBREPLACE_HOSTCC',
        REPLACE_HOSTCC_SOURCE,
        use_hostcc=True,
        use_global_deps=False,
        group='hostcc_base_build_main',
        deps = extra_libs
    )"""
new="""    if not bld.CONFIG_SET('SAMBA_SKIP_HOSTCC'):
        bld.SAMBA_SUBSYSTEM('LIBREPLACE_HOSTCC',
            REPLACE_HOSTCC_SOURCE,
            use_hostcc=True,
            use_global_deps=False,
            group='hostcc_base_build_main',
            deps = extra_libs
        )"""
assert old in s
open(p,'w').write(s.replace(old,new))

p='third_party/heimdal_build/wscript_build'
s=open(p).read()
import re
for name, block in [
 ('ROKEN_HOSTCC', """    HEIMDAL_SUBSYSTEM('ROKEN_HOSTCC',
        ROKEN_HOSTCC_SOURCE,
        use_hostcc=True,
        use_global_deps=False,
        includes='../heimdal/lib/roken ../heimdal/include ../heimdal_build/include',
        group='hostcc_base_build_main',
        deps='LIBREPLACE_HOSTCC',
        )"""),
 ('HEIMBASE_HOSTCC', """    HEIMDAL_SUBSYSTEM('HEIMBASE_HOSTCC',
        HEIMBASE_HOSTCC_SOURCE,
        use_hostcc=True,
        use_global_deps=False,
        includes='../heimdal/lib/base ../heimdal/lib/com_err ../heimdal/include ../heimdal/lib/krb5',
        group='hostcc_build_main',
        deps='ROKEN_HOSTCC LIBREPLACE_HOSTCC',
        )"""),
 ('HEIMDAL_VERS_HOSTCC', """HEIMDAL_SUBSYSTEM('HEIMDAL_VERS_HOSTCC',
       'lib/vers/print_version.c ../heimdal_build/version.c',
       group='hostcc_base_build_main',
       deps='LIBREPLACE_HOSTCC ROKEN_HOSTCC',
       use_global_deps=False,
       use_hostcc=True)"""),
]:
    assert block in s, f"缺少 {name} 块"
    # 检测首行缩进，按相同缩进输出 guard，并把块体再缩进 4 空格。
    lines = block.splitlines()
    indent = re.match(r'^(\s*)', lines[0]).group(1)
    reindented = '\n'.join(indent + '    ' + l[len(indent):] if l.startswith(indent) else '    ' + l for l in lines)
    s = s.replace(block, f"{indent}if not bld.CONFIG_SET('SAMBA_SKIP_HOSTCC'):\n{reindented}")
open(p,'w').write(s)
PY

  # 补丁 7：残留 HostCC 任务会错误复用 target 配置；显式交叉构建宏同时
  # 传给 target 与 HostCC，可靠地避免它们包含 macOS 上不可用的 malloc.h。
  python3 - <<'PY'
p='lib/replace/replace.h'
s=open(p).read()
old="""#ifdef HAVE_MALLOC_H
#include <malloc.h>
#endif"""
new="""#if defined(HAVE_MALLOC_H) && !defined(SAMBA_OHOS_CROSS)
#include <malloc.h>
#endif"""
assert old in s
open(p,'w').write(s.replace(old,new,1))
PY

  # 补丁 8：smbclient 交叉构建时禁用 pidl --python，避免 host C 类型
  #   (timeval, files_struct, db_record, smbXsrv_tcon_table 等) 解析失败。
  python3 - <<'PY'
p='source3/librpc/idl/wscript_build'
s=open(p).read()
old="options='--includedir=%s --header --ndr-parser --client --python' % topinclude"
new="options='--includedir=%s --header --ndr-parser --client' % topinclude"
assert old in s, "smbXsrv pidl --python 选项字符串未找到"
open(p,'w').write(s.replace(old,new,1))
PY
}

# ---------------- 交叉回答 ----------------
write_cross_answers() {
  mkdir -p "$SAMBA_DIR/build-cache"
  cat > "$SAMBA_DIR/build-cache/cross-answers.txt" <<'EOF'
Checking uname sysname type: "Linux"
Checking uname machine type: "aarch64"
Checking uname release type: "5.10.0"
Checking uname version type: "#1 SMP OpenHarmony"
rpath library support: OK
-Wl,--version-script support: OK
Checking getconf LFS_CFLAGS: ""
Checking for large file support without additional flags: OK
Checking for -D_FILE_OFFSET_BITS=64: OK
Checking for -D_LARGE_FILES: NO
Checking getconf large file support flags work: NO
Checking correct behavior of strtoll: OK
Checking for working strptime: OK
Checking for C99 vsnprintf: OK
Checking for HAVE_SHARED_MMAP: OK
Checking for HAVE_MREMAP: OK
Checking for HAVE_INCOHERENT_MMAP: NO
Checking for HAVE_SECURE_MKSTEMP: OK
Checking value of NSIG: 65
Checking value of _NSIG: 65
Checking value of SIGRTMAX: 64
Checking value of SIGRTMIN: 35
Checking for a 64-bit host to support lmdb: OK
Checking errno of iconv for illegal multibyte sequence: 84
Checking for gnutls fips mode support: NO
Checking for *bsd style statfs with statfs.f_iosize: NO
Checking if can we convert from CP850 to UCS-2LE: NO
Checking if can we convert from IBM850 to UCS-2LE: NO
Checking if can we convert from UTF-8 to UCS-2LE: OK
Checking if can we convert from UTF8 to UCS-2LE: OK
vfs_fileid checking for statfs() and struct statfs.f_fsid: OK
Checking whether setreuid is available: OK
Checking whether setresuid is available: OK
Checking whether seteuid is available: OK
Checking whether fcntl locking is available: OK
Checking whether fcntl lock supports open file description locks: NO
Checking whether fcntl supports flags to send direct I/O availability signals: NO
Checking whether fcntl supports setting/getting hints: NO
Checking for the maximum value of the 'time_t' type: 9223372036854775807
Checking whether the realpath function allows a NULL argument: OK
Checking for ftruncate extend: OK
Checking for readlink breakage: NO
getcwd takes a NULL argument: OK
for QUOTACTL_4A: long quotactl(int cmd, char *special, qid_t id, caddr_t addr): NO
EOF
}

# ---------------- 原生 host 工具预编译 ----------------
build_host_tools() {
  log "原生预编译 host 工具 (compile_et / asn1_compile)"
  if [ ! -d "$SAMBA_HOST_DIR/.git" ]; then
    git_clone_retry https://gitlab.com/samba-team/samba.git "$SAMBA_HOST_DIR"
  fi
  ( cd "$SAMBA_HOST_DIR" && git checkout "$SAMBA_COMMIT" && git reset --hard "$SAMBA_COMMIT" && git clean -fd )
  # 复用交叉树的 buildtools/bin/waf（rsync 已排除 bin）。
  [ -f "$SAMBA_HOST_DIR/buildtools/bin/waf" ] || rsync -a "$SAMBA_DIR/buildtools/bin/" "$SAMBA_HOST_DIR/buildtools/bin/"
  # bin/wscript 缺失会导致 waf ant_glob 扫描失败；占位即可。
  mkdir -p "$SAMBA_HOST_DIR/bin"
  [ -f "$SAMBA_HOST_DIR/bin/wscript" ] || printf 'def build(bld):\n    pass\n' > "$SAMBA_HOST_DIR/bin/wscript"

  # host 构建只需 compile_et / asn1_compile, 不实际链接 GnuTLS。
  # 提供占位 gnutls.pc 以通过 Samba configure 的 mandatory CHECK_CFG 版本检查。
  # CHECK_CFG 仅调用 pkg-config 检查版本, 不编译测试程序; 后续非 mandatory 的
  # CHECK_CODE(fips) 会失败但不阻断 configure。
  local host_pc="$WORK_DIR/host-pkgconfig"; mkdir -p "$host_pc/gnutls"
  cat > "$host_pc/gnutls.pc" <<'PC'
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: GnuTLS
Description: GnuTLS placeholder for host tool build
Version: 3.8.0
Cflags: -I${includedir}
Libs: -L${libdir} -lgnutls
PC
  : > "$host_pc/gnutls/gnutls.h"

  # 原生环境（清空交叉变量）。覆盖 x64(/usr/local) 和 arm64(/opt/homebrew) Homebrew 路径。
  # 同时透传 -I/-L 让 waf 完整 build 中触发 genrand.c 等引用 gnutls.h 的源文件能找到头。
  # host build 不需要真的链接 gnutls, 仅需 include 可见。
  env -i HOME="$HOME" PATH="$PREFIX/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin" \
    PKG_CONFIG_PATH="$host_pc:/usr/local/lib/pkgconfig:/opt/homebrew/lib/pkgconfig:/usr/lib/pkgconfig" \
    bash -c "cd '$SAMBA_HOST_DIR' && \
      unset CC CXX PKG_CONFIG_LIBDIR && \
      export CFLAGS='-I$PREFIX/include' CXXFLAGS='-I$PREFIX/include' \
             CPPFLAGS='-I$PREFIX/include' LDFLAGS='-L$PREFIX/lib' && \
      PYTHONHASHSEED=1 ./configure --disable-python --without-ad-dc --disable-fault-handling \
        --without-ldb-lmdb --without-gettext --without-json --without-systemd --without-libarchive \
        --without-acl-support --without-ldap --without-ads --without-pam && \
      PYTHONHASHSEED=1 python3 buildtools/bin/waf build --targets=compile_et,asn1_compile -j$JOBS"

  # HEIMDAL_BINARY 的 target 输出位于模块目录，而不是 bin/default 根目录。
  local waf_out="$SAMBA_HOST_DIR/bin/default/third_party/heimdal_build"
  if [ ! -x "$waf_out/compile_et" ] || [ ! -x "$waf_out/asn1_compile" ]; then
    die "host 工具生成位置不符预期: $waf_out (compile_et/asn1_compile 不存在)"
  fi
  mkdir -p "$SAMBA_DIR/bin"
  cp "$waf_out/asn1_compile" "$SAMBA_DIR/bin/asn1_compile"
  cp "$waf_out/compile_et" "$SAMBA_DIR/bin/compile_et"
  chmod +x "$SAMBA_DIR/bin/asn1_compile" "$SAMBA_DIR/bin/compile_et"
}

# ---------------- Samba 交叉配置 + 构建 ----------------
configure_samba() {
  log "交叉配置 Samba"
  cd "$SAMBA_DIR"
  [ -f bin/asn1_compile ] && [ -f bin/compile_et ] || die "host 工具缺失"
  ./configure \
    --cross-compile --cross-answers=build-cache/cross-answers.txt \
    --host=$HOST_TRIPLET --hostcc=/usr/bin/clang \
    --bundled-libraries=ALL --private-libraries=ALL \
    --with-static-modules='ALL' --with-shared-modules='!DEFAULT' \
    --disable-python --without-ad-dc --disable-fault-handling \
    --without-ldb-lmdb --without-gettext --without-json \
    --without-systemd --without-libarchive --without-acl-support \
    --without-ldap --without-ads --without-pam
}

build_samba() {
  log "交叉构建 Samba libsmbclient"
  cd "$SAMBA_DIR"
  PYTHONHASHSEED=1 python3 buildtools/bin/waf build --targets=smbclient -j"$JOBS"
}

# ---------------- 生成静态库 + pkg-config ----------------
install_libsmbclient() {
  log "归档 libsmbclient.a 并安装"
  local ar="$TOOLCHAIN/llvm-ar"
  find "$SAMBA_DIR/bin/default" -name "*.o" -print > "$WORK_DIR/objlist.txt"
  "$ar" rcs "$PREFIX/lib/libsmbclient.a" $(cat "$WORK_DIR/objlist.txt")
  cp "$SAMBA_DIR/bin/default/include/public/libsmbclient.h" "$PREFIX/include/libsmbclient.h"

  cat > "$PREFIX/lib/pkgconfig/smbclient.pc" <<EOF
prefix=$PREFIX
exec_prefix=\${prefix}
libdir=\${exec_prefix}/lib
includedir=\${prefix}/include

Name: smbclient
Description: libsmbclient (Samba client) - static build for OpenHarmony ARM64
Version: 4.20.7
URL: https://www.samba.org/
Libs: -L\${libdir} -lsmbclient
Libs.private: -lgnutls -ltasn1 -lnettle -lhogweed -lgmp -lz -lpopt
Cflags: -I\${includedir}
EOF

  log "校验 smbc_* 符号"
  "$TOOLCHAIN/llvm-nm" --defined-only "$PREFIX/lib/libsmbclient.a" | grep -E ' T smbc_(open|read|init_context|opendir|readdir|stat|close)' | head
  log "libsmbclient 静态库就绪：$PREFIX/lib/libsmbclient.a"
}

# ---------------- 主流程 ----------------
main() {
  fetch_samba
  build_modern_bison || die "无法提供现代 bison"
  setup_cross_env
  clean_src
  build_dependencies
  patch_samba_source
  write_cross_answers
  # 先准备 host 工具目录以接收交叉树补丁之外的原始源码。
  build_host_tools
  configure_samba
  build_samba
  install_libsmbclient
  log "受控 libsmbclient 构建完成。sysroot：$PREFIX"
}

main "$@"
