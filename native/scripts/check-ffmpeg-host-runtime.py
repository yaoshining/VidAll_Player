"""检查 FFmpeg SDK 是否提供 Player 必需的 SMB 沙箱配置接口。

这是宿主运行时的前置门禁，不替代完整 SDK、链接或设备验收。
软件解码不要求 av_ohcodec_*，但仍需真实的 SMB 配置实现。
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

SYMBOL = 'ohcodec_smb_runtime_configure_v1'


def inspect_sdk(root, nm, abi):
    root = Path(root)
    header = root / 'include/libavformat/ohcodec_smb_runtime.h'
    library = root / 'lib/libavformat.so.62'
    errors = []
    result = {'abi': abi, 'requiredSymbol': SYMBOL, 'errors': errors,
              'scope': '仅 SMB 宿主运行时前置合同；不代表完整 SDK 或设备验收'}
    if not header.is_file():
        errors.append('缺少配套头文件 include/libavformat/ohcodec_smb_runtime.h')
    else:
        result['headerSHA256'] = hashlib.sha256(header.read_bytes()).hexdigest()
    if not library.is_file():
        errors.append('缺少 lib/libavformat.so.62')
    else:
        data = library.read_bytes()
        result['librarySHA256'] = hashlib.sha256(data).hexdigest()
        machine = {'x86_64': 62, 'arm64-v8a': 183}[abi]
        if (len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01'
                or struct.unpack_from('<HH', data, 16) != (3, machine)):
            errors.append('不是目标架构的 ELF64 共享库：' + abi)
        else:
            try:
                text = subprocess.check_output(
                    [str(nm), '-D', '--defined-only', str(library)], text=True,
                    stderr=subprocess.STDOUT)
                # 必须是真正的动态函数定义，不能接受 UND 或相似名称。
                exports = set()
                for line in text.splitlines():
                    match = re.fullmatch(r'\s*[0-9a-fA-F]+\s+[TW]\s+(\S+)\s*', line)
                    if match:
                        exports.add(match[1].split('@')[0])
                result['symbolExported'] = SYMBOL in exports
                if SYMBOL not in exports:
                    errors.append('缺少动态导出 ' + SYMBOL)
            except (OSError, subprocess.CalledProcessError) as exc:
                errors.append('无法核验动态导出：' + str(exc))
    result['passed'] = not errors
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--nm', type=Path, required=True)
    parser.add_argument('--abi', choices=['x86_64', 'arm64-v8a'], required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = inspect_sdk(args.sdk, args.nm, args.abi)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')
    raise SystemExit(0 if report['passed'] else 1)
