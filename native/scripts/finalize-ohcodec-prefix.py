#!/usr/bin/env python3
"""从本轮 FFmpeg 配置和 ELF 生成 bootstrap 所需 prefix 元数据。"""
import argparse
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess

LIBRARIES = ['libavcodec.so.62', 'libavformat.so.62', 'libavutil.so.60',
             'libavfilter.so.11', 'libswresample.so.6', 'libswscale.so.9']


def finalize(root, ndk):
    prefix = root / 'prefix'
    config = (root / 'build/config.h').read_text() + (root / 'build/config_components.h').read_text()
    for feature in ['CONFIG_OHCODEC', 'CONFIG_GNUTLS', 'CONFIG_LIBSMBCLIENT', 'CONFIG_HTTPS_PROTOCOL', 'CONFIG_TLS_PROTOCOL']:
        if not re.search(r'^#define ' + feature + r' 1$', config, re.M):
            raise ValueError('实际构建未启用 ' + feature)
    report = []
    for name in LIBRARIES:
        library = prefix / 'lib' / name
        if not library.is_file():
            raise FileNotFoundError(library)
        elf = subprocess.check_output([str(ndk / 'llvm/bin/llvm-readelf'), '-h', '-d', str(library)], text=True)
        if not re.search(r'Machine:\s*AArch64\s*$', elf, re.M):
            raise ValueError(name + ' 不是 AArch64')
        if re.search(r'Shared library: \[lib(?:smbclient|gnutls|nettle|hogweed|gmp|tasn1|popt)[^\]]*\]', elf):
            raise ValueError(name + ' 存在未静态闭合的 SMB/TLS 依赖')
        report.append(name + '\n' + elf)
    source = dict(line.split('=', 1) for line in (root / 'SOURCE.txt').read_text().splitlines())
    options = shlex.split((root / 'build/ffbuild/config.log').read_text().splitlines()[0][2:])[1:]
    licenses = prefix / 'licenses'
    licenses.mkdir(exist_ok=True)
    for name, output in [('COPYING.GPLv3', 'GPL-3.0-or-later.txt'), ('COPYING.LGPLv2.1', 'FFmpeg-LGPL-2.1-or-later.txt')]:
        shutil.copy2(root / 'source' / name, licenses / output)
    (prefix / 'VERSION').write_text('\n'.join([
        'ffmpeg_version=8.0', 'source_commit=' + source['ffmpeg_commit'],
        'ohcodec_patch_commit=' + source['builder_commit'], 'ohcodec=enabled',
        'libsmbclient=enabled', 'libsmbclient_linkage=static-closure',
        'smb_patch=native/patches/ffmpeg-runtime/0001-libsmbclient-private-credentials.patch',
        'architecture=arm64-v8a', 'target=aarch64-unknown-linux-ohos', 'elf_machine=AArch64',
        'https_protocol=enabled', 'tls_protocol=enabled', 'tls_backend=gnutls',
        'tls_backend_linkage=static-closure']) + '\n')
    (prefix / 'configure-options.txt').write_text('\n'.join(options) + '\n')
    (prefix / 'ELF-REPORT.txt').write_text('\n'.join(report))
    (prefix / 'MANIFEST.tsv').write_text('path\tsize_bytes\tsha256\n' + ''.join(
        f'{p.relative_to(prefix)}\t{p.stat().st_size}\t{hashlib.sha256(p.read_bytes()).hexdigest()}\n'
        for p in sorted(prefix.rglob('*')) if p.is_file() and p.name != 'MANIFEST.tsv'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--ndk', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.root, args.ndk)
