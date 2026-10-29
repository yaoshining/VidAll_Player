#!/usr/bin/env python3
"""HAR 与实际 consumer 的 ARM64 固定八库和当次 NAPI 字节传递门禁。"""
import argparse, hashlib, json, os, re, shutil, subprocess, tarfile, tempfile, zipfile
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[2]
NAMES = {'libmpv.so', 'libavcodec.so.62', 'libavformat.so.62', 'libavfilter.so.11', 'libavutil.so.60', 'libswresample.so.6', 'libswscale.so.9', 'libc++_shared.so'}
BRIDGE = 'libvidall_player_native.so'

def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix() != name.rstrip('/'):
        raise ValueError('归档路径异常')

def libraries(path, har):
    files = {}; seen = set(); prefix = 'package/libs/' if har else 'libs/'
    with tarfile.open(path, 'r:*') if har else zipfile.ZipFile(path) as archive:
        entries = archive.getmembers() if har else archive.infolist()
        for entry in entries:
            name = entry.name if har else entry.filename
            safe_name(name)
            if name.rstrip('/') in seen: raise ValueError('归档重复成员')
            seen.add(name.rstrip('/'))
            directory = entry.isdir() if har else entry.is_dir()
            if har and not (entry.isfile() or directory): raise ValueError('HAR 链接或特殊成员拒绝')
            if not har and (entry.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('HAP 符号链接拒绝')
            if directory or not name.startswith(prefix): continue
            tail = name[len(prefix):]
            if tail not in {'arm64-v8a/' + n for n in NAMES | {BRIDGE}}: raise ValueError('非预期架构或库成员')
            stream = archive.extractfile(entry) if har else archive.open(entry)
            with stream: data = stream.read()
            if len(data) < 20 or data[:6] != b'\x7fELF\x02\x01' or int.from_bytes(data[18:20], 'little') != 183:
                raise ValueError('库不是 ARM64 ELF')
            files[tail.split('/')[-1]] = data
    if set(files) != NAMES | {BRIDGE}: raise ValueError('ARM64 九库集合不完整')
    return files

def verify(har, hap, records, readelf):
    expected = {Path(r['path']).name: r['sha256'] for r in records}
    if len(records) != 8 or set(expected) != NAMES: raise ValueError('固定八库清单不准确或重复')
    first, second = libraries(har, True), libraries(hap, False)
    digest = lambda data: hashlib.sha256(data).hexdigest()
    for name in NAMES:
        if digest(first[name]) != expected[name]: raise ValueError('HAR 核心库不匹配固定来源：' + name)
    if first != second: raise ValueError('consumer 九库不是同一 HAR 的字节')
    # 不解包归档，只给实际 llvm-readelf 一个受控临时文件；保留旧动态依赖/RPATH 检查。
    with tempfile.TemporaryDirectory() as folder:
        native = Path(folder) / BRIDGE; native.write_bytes(first[BRIDGE])
        result = subprocess.run([str(readelf), '-d', str(native)], capture_output=True, text=True, timeout=20)
        if result.returncode != 0: raise ValueError('NAPI 动态段读取失败')
        if not re.search(r'Shared library: \[libmpv\.so\]', result.stdout): raise ValueError('NAPI 缺少 libmpv DT_NEEDED')
        if re.search(r'\((RPATH|RUNPATH)\)', result.stdout): raise ValueError('NAPI 不得携带 RPATH/RUNPATH')
    return {'passed': True, 'libraries': {n: digest(d) for n,d in sorted(first.items())}, 'deviceVerified': False, 'formalArtifactAllowed': False}

def main():
    p = argparse.ArgumentParser(); p.add_argument('--har', type=Path, required=True); p.add_argument('--hap', type=Path, required=True)
    p.add_argument('--readelf', default=os.environ.get('LLVM_READELF') or shutil.which('llvm-readelf') or str(Path(os.environ.get('OHOS_NDK', '/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))/'native/llvm/bin/llvm-readelf'))
    a = p.parse_args(); records = json.loads((ROOT/'release/inputs/004-normal-core/manifest.json').read_text())['libraries']
    print(json.dumps(verify(a.har, a.hap, records, a.readelf), ensure_ascii=False))
if __name__ == '__main__': main()
