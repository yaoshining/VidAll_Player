"""为宿主音频回归派生与交付核心相同的源文件；不构建 FFmpeg 或播放器。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT/'native/tests/audio-interrupt/ci-input-lock.json'
RECOVERY = ROOT/'release/inputs/004-normal-core/provenance/host-recovery-input.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('输入路径越界：'+value)
    return path


def verify(path, expected, label):
    if not path.is_file() or path.is_symlink() or digest(path) != expected:
        raise ValueError(label+'摘要不匹配：'+str(path))


def prepare(repo, source, output, contract, recovery):
    if output.exists():
        raise FileExistsError(output)
    commit = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit != contract['upstreamCommit']:
        raise ValueError('上游提交不匹配')
    verify(repo/'release/inputs/004-normal-core/arm64-v8a/libmpv.so',contract['mpvLibrarySHA256'],'交付核心')
    files = contract['files']
    for file, row in files.items():
        verify(source/relative(file),row['baselineSHA256'],'基线源码')
    for entry in recovery['patches'] + recovery['addedSources']:
        verify(repo/relative(entry['path']),entry['sha256'],'恢复输入')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        work = Path(temp)/'audio-source';work.mkdir()
        for file in files:
            target = work/file;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/file,target)
        for entry in recovery['patches']:
            patch = (repo/entry['path']).resolve()
            touched = set(re.findall(r'^\+\+\+ b/(.+)$',patch.read_text(),re.M))
            if touched.intersection(files):
                subprocess.run(['git','apply',*['--include='+file for file in files],str(patch)],cwd=work,
                               env={**os.environ,'GIT_CEILING_DIRECTORIES':str(work.parent.resolve())},check=True)
        for file, row in files.items():
            verify(work/file,row['patchedSHA256'],'派生源码')
        result = {'upstreamCommit':commit,'mpvLibrarySHA256':contract['mpvLibrarySHA256'],
                  'files':{file:digest(work/file) for file in files},
                  'scope':'仅宿主音频函数回归；不代表目标设备音频与焦点验收'}
        (work/'audio-input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        work.rename(output)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(ROOT,args.source,args.output,json.loads(CONTRACT.read_text()),
                             json.loads(RECOVERY.read_text())),ensure_ascii=False,indent=2))
