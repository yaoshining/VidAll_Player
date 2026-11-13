#!/usr/bin/env python3
"""核验显式导出的证据块，完整通过后才写入指定文件。"""
import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re

CHUNK = 262144
LIMIT = 16777216


def assemble(packets):
    parts = []
    meta = None
    for packet in packets:
        if not isinstance(packet, dict):
            raise ValueError('证据块不是对象')
        if packet.get('version') != 'spec017-evidence-v1' or packet.get('kind') not in ('capture', 'events'):
            raise ValueError('证据版本或类型不支持')
        if any(type(packet.get(k)) is not int for k in ('bytes', 'chunks', 'index')):
            raise ValueError('长度或序号不是整数')
        size, count, index = (packet[k] for k in ('bytes', 'chunks', 'index'))
        digest = packet.get('sha256')
        if not 1 <= size <= LIMIT or count != (size + CHUNK - 1) // CHUNK or not 0 <= index < count:
            raise ValueError('长度、块数或序号越界')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('哈希格式错误')
        identity = (packet['kind'], size, count, digest)
        if meta is not None and meta != identity:
            raise ValueError('混入其他文件或其他快照')
        meta = identity
        encoded = packet.get('data')
        if not isinstance(encoded, str) or len(encoded) > 4 * ((CHUNK + 2) // 3):
            raise ValueError('编码数据长度异常')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError('编码数据损坏') from error
        if len(data) != min(CHUNK, size - index * CHUNK):
            raise ValueError('数据块被截断或长度不符')
        if index < len(parts):
            if parts[index] != data:
                raise ValueError('重发内容冲突')
        elif index == len(parts):
            parts.append(data)
        else:
            raise ValueError('数据块缺失或乱序')
    if meta is None or len(parts) != meta[2]:
        raise ValueError('证据块不完整')
    result = b''.join(parts)
    if len(result) != meta[1] or hashlib.sha256(result).hexdigest() != meta[3]:
        raise ValueError('文件长度或SHA256不符')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('chunks', nargs='+', type=Path)
    args = parser.parse_args()
    if len(args.chunks) > 256:
        parser.error('一次最多256个块文件（含重发）')
    def packets():
        for path in args.chunks:
            if path.stat().st_size > 400000:
                raise ValueError('块文件过大')
            yield json.loads(path.read_text())
    result = assemble(packets())
    # 不覆盖已有证据；包中的内容不能决定写入路径。
    with args.out.open('xb') as output:
        output.write(result)
    print(json.dumps({'bytes': len(result), 'sha256': hashlib.sha256(result).hexdigest(), 'output': str(args.out)}))


if __name__ == '__main__': main()
