"""核对旧版候选清单与本地实物；成功只表示完整性通过，不代表发布审批。"""
import argparse
import datetime
import hashlib
import json
import posixpath
from pathlib import Path
import re
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'release/manifests/candidate-003-libmpv-player-har.json'
HAR_MEMBER = 'package/libs/arm64-v8a/libmpv.so'


def sha256(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


def verify(root, manifest_path):
    report = {
        'schemaVersion': 1,
        'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'manifest': str(manifest_path),
        'status': 'failed', 'checks': {}, 'errors': [],
        'scope': '核对源库 SHA-256、HAR 内库 SHA-256、HAR 体积及新版清单的完整 HAR SHA-256；不代表构建可复现、真机验证或发布批准。',
    }

    def compare(name, expected, actual):
        report['checks'][name] = {
            'expected': expected, 'actual': actual, 'matches': expected == actual,
        }
        if expected != actual:
            report['errors'].append(f'{name} 不一致：期望 {expected}，实际 {actual}')

    try:
        manifest = json.loads((root / manifest_path).read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('候选清单必须是 JSON 对象')
        version = manifest.get('schemaVersion', 1)
        if type(version) is not int or version not in (1, 2):
            raise ValueError('不支持的候选清单版本')
        report['candidateId'] = manifest['candidateId']
        arm64 = manifest['loadingBoundary']['cmakeLogic']['arm64_v8a']
        har = manifest['arm64Deliverables']['har']
        for key in ('libmpvSha256', 'libmpvStrippedSha256'):
            if not isinstance(arm64[key], str) or not re.fullmatch('[0-9a-f]{64}', arm64[key]):
                raise ValueError(f'{key} 必须为完整的小写 SHA-256')
        if type(har['sizeBytes']) is not int or har['sizeBytes'] <= 0:
            raise ValueError('HAR sizeBytes 必须为正整数')
        def input_path(relative):
            path = (root / relative).resolve()
            if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
                raise ValueError('候选实物路径超出根目录')
            return path

        with input_path(arm64['libmpvSource']).open('rb') as stream:
            compare('sourceSha256', arm64['libmpvSha256'], sha256(stream))
        har_path = input_path(har['path'])
        compare('harSizeBytes', har['sizeBytes'], har_path.stat().st_size)
        if manifest.get('schemaVersion') == 2 or 'sha256' in har:
            if not isinstance(har['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', har['sha256']):
                raise ValueError('HAR sha256 必须为完整的小写 SHA-256')
            with har_path.open('rb') as stream:
                compare('harSha256', har['sha256'], sha256(stream))
        with tarfile.open(har_path, 'r:*') as archive:
            members = [m for m in archive.getmembers() if posixpath.normpath(m.name) == HAR_MEMBER]
            if (len(members) != 1 or members[0].name.removeprefix('./') != HAR_MEMBER
                    or members[0].type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or members[0].sparse is not None):
                raise ValueError(f'HAR 必须包含唯一的普通文件 {HAR_MEMBER}')
            with archive.extractfile(members[0]) as stream:
                compare('harLibmpvSha256', arm64['libmpvStrippedSha256'], sha256(stream))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, EOFError) as error:
        report['errors'].append(f'候选完整性校验失败：{error}')
    if not report['errors']:
        report['status'] = 'passed'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='项目根目录')
    parser.add_argument('--manifest', type=Path, default=Path(MANIFEST), help='候选清单，相对项目根目录')
    parser.add_argument('--output', type=Path, help='审计报告输出路径')
    args = parser.parse_args()
    report = verify(args.root, args.manifest)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open('x', encoding='utf-8') as output:
                output.write(rendered)
        except OSError as error:
            parser.error(f'无法创建新报告：{error}')
    print(rendered, end='')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
