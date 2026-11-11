"""校验封存基线、预编译 FFmpeg SDK 与 Player 补丁，生成独立 mpv 构建输入。"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT/'release/inputs/004-normal-core/provenance/host-recovery-input.json'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('输入路径越界：'+value)
    return path

def verified(path, digest):
    if not path.is_file() or sha(path) != digest:
        raise ValueError('输入摘要不匹配：'+str(path))

def prepare(repo, lock, baseline, dependencies, mpv, sdk, output):
    """不修改来源、不编译 FFmpeg；只有全部校验成功才发布输入目录。"""
    if output.exists():
        raise FileExistsError(output)
    verified(baseline, lock['baselineManifestSHA256'])
    verified(sdk/'manifest.json', lock['ffmpegManifestSHA256'])
    manifest = json.loads(baseline.read_text())
    sdk_manifest = json.loads((sdk/'manifest.json').read_text())
    for entry in sdk_manifest['files']:
        verified(sdk/relative(entry['path']), entry['sha256'])
    for entry in lock['patches'] + lock['addedSources']:
        verified(repo/relative(entry['path']), entry['sha256'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        work = Path(temp)/'package';work.mkdir()
        def copy(source, target, digest):
            verified(source, digest)
            dest = work/relative(target)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        for entry in manifest['files']:
            path = relative(entry['path'])
            if path.parts[0] == 'ffmpeg':
                continue
            source = mpv/path.relative_to('sources/mpv') if str(path).startswith('sources/mpv/') else dependencies/path
            copy(source, str(path), entry['sha256'])
        for entry in sdk_manifest['files']:
            path = relative(entry['path'])
            if path.parts[0] in ('include', 'lib', 'share'):
                copy(sdk/path, 'ffmpeg/'+str(path), entry['sha256'])
        for entry in lock['patches']:
            subprocess.run(['git','apply','--directory=sources/mpv',str((repo/entry['path']).resolve())],cwd=work,check=True,
                           env={**os.environ,'GIT_CEILING_DIRECTORIES':str(work.parent.resolve())})
        for entry in lock['addedSources']:
            target = relative(entry['target'])
            if (work/'sources/mpv'/target).exists():
                raise ValueError('新增源码不能覆盖封存文件：'+str(target))
            copy(repo/entry['path'], 'sources/mpv/'+str(target), entry['sha256'])
        prefixes = set()
        for entry in sdk_manifest['files']:
            if entry['path'].startswith('lib/pkgconfig/'):
                for line in (sdk/entry['path']).read_text().splitlines():
                    if line.startswith('prefix='):
                        prefixes.add(line[7:])
        manifest['relocations'] += [{'from':prefix,'to':'ffmpeg'} for prefix in sorted(prefixes)]
        manifest['files'] = [{'path':p.relative_to(work).as_posix(),'size':p.stat().st_size,'sha256':sha(p)}
                             for p in sorted(work.rglob('*')) if p.is_file()]
        manifest['hostRecovery'] = lock
        (work/'package.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        work.rename(output)
    return sha(output/'package.json')
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','dependencies','mpv','sdk','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    print(prepare(ROOT,json.loads(LOCK.read_text()),args.baseline,args.dependencies,args.mpv,args.sdk,args.output))
