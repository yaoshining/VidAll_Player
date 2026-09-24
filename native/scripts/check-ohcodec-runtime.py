#!/usr/bin/env python3
"""校验宿主 FFmpeg 和 libmpv 必须同时包含 OHCodec，不能仅检查配置声明。"""
import argparse
import pathlib
import subprocess


def exported_symbols(output):
    """按完整符号名匹配，同时兼容 ELF 符号版本后缀。"""
    return {line.split()[-1].split('@', 1)[0] for line in output.splitlines() if line.split()}


def inspect_pair(codec, util, mpv, nm):
    failures = []
    if b'h264_ohcodec\0' not in pathlib.Path(codec).read_bytes():
        failures.append('libavcodec 缺少 h264_ohcodec 解码器')
    if b'hevc_ohcodec\0' not in pathlib.Path(codec).read_bytes():
        failures.append('libavcodec 缺少 hevc_ohcodec 解码器')
    exports = subprocess.check_output([nm, '-D', '--defined-only', str(util)], text=True)
    # 桥接使用该符号；同名 SONAME 并不保证私有扩展 ABI 完整。
    if 'av_ohcodec_release_buffer' not in exported_symbols(exports):
        codec_exports = subprocess.check_output([nm, '-D', '--defined-only', str(codec)], text=True)
        if 'av_ohcodec_release_buffer' not in exported_symbols(codec_exports):
            failures.append('FFmpeg 缺少 av_ohcodec_release_buffer 导出')
    if b'OHCodec Surface hwdec requires compatible GL or Vulkan.' not in pathlib.Path(mpv).read_bytes():
        failures.append('libmpv 缺少 OHCodec Surface 互操作桥接')
    return failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['codec', 'util', 'mpv', 'nm']:
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    failures = inspect_pair(args.codec, args.util, args.mpv, args.nm)
    print('\n'.join(failures) if failures else 'OHCodec 配套产物检查通过')
    raise SystemExit(bool(failures))
