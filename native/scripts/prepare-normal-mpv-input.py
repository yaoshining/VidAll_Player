"""从 Phase30 A 封存输入派生只修改 mpv 的构建副本，供原 fresh_build.py 使用。"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_LOCK = ROOT / 'release/inputs/004-normal-core/provenance/source-lock.json'

def digest(path):
    """按文件内容计算来源清单使用的 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(source, output):
    """校验 Phase30 A 归档，并在独立副本中应用锁定的 mpv 补丁。"""
    update = json.loads(SOURCE_LOCK.read_text())['mpvUpdate']
    patch = ROOT / update['patch']
    if digest(patch) != update['patchSHA256']:
        raise ValueError('mpv 补丁与来源锁不匹配')
    if digest(source / 'package.json') != update['baselineInputSHA256']:
        raise ValueError('输入须为封存的 Phase30 A package.json')
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('构建副本必须位于输入目录外')
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((source / 'package.json').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        work = Path(temp) / 'package'
        for row in manifest['files']:
            dest = work / row['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / row['path'], dest)
            if digest(dest) != row['sha256']:
                raise ValueError('封存输入不匹配：' + row['path'])
        # 副本可位于另一个 checkout 内；禁止 git 发现父仓库后静默跳过补丁。
        subprocess.run(['git', 'apply', '--directory=sources/mpv', str(patch)], cwd=work, check=True,
                       env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(work.resolve().parent)})
        for row in manifest['files']:
            if row['path'].startswith('sources/mpv/'):
                path = work / row['path']
                row.update(size=path.stat().st_size, sha256=digest(path))
        (work / 'package.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        if digest(work / 'package.json') != update['patchedInputSHA256']:
            raise ValueError('派生输入清单与已验证的 mpv 构建不匹配')
        work.rename(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
