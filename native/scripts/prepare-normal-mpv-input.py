"""从 Phase30 A 封存输入派生只修改 mpv 的构建副本，供原 fresh_build.py 使用。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE_PACKAGE_SHA = 'ba6747a77f6d4a18d2cd004f0301b2cb6f1aa940be1fa2bad0b1bd38bcd78fc4'
ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'native/patches/mpv/0001-ohaudio-legacy-interrupt.patch'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(source, output):
    if digest(source / 'package.json') != BASE_PACKAGE_SHA:
        raise ValueError('输入须为封存的 Phase30 A package.json')
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('构建副本必须位于输入目录外')
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((source / 'package.json').read_text())
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        work = Path(temp) / 'package'
        for row in manifest['files']:
            dest = work / row['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / row['path'], dest)
            if digest(dest) != row['sha256']:
                raise ValueError('封存输入不匹配：' + row['path'])
        subprocess.run(['git', 'apply', '--directory=sources/mpv', str(PATCH)], cwd=work, check=True)
        for row in manifest['files']:
            if row['path'].startswith('sources/mpv/'):
                path = work / row['path']
                row.update(size=path.stat().st_size, sha256=digest(path))
        (work / 'package.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        work.rename(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
