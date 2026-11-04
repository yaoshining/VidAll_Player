#!/usr/bin/env python3
"""核对来源声明、缓存观察和材料摘要；不替代源码重建或许可证复核。"""
import argparse
import hashlib
import json
from pathlib import Path


def check_observed_sboms(observed, cdx, spdx):
    """观察 SBOM 必须与证据清单同名同版本，不得冒充许可证结论。"""
    expected = {c['name']: c for c in observed['components']}
    issues = []
    for kind, entries in [('cdx', cdx['components']), ('spdx', spdx['packages'])]:
        actual = {c['name']: c for c in entries}
        if len(actual) != len(entries) or set(actual) != set(expected):
            issues.append({'code': 'observed-' + kind + '-mismatch', 'component': None})
        for name, o in expected.items():
            c = actual.get(name, {})
            if kind == 'cdx':
                good = c.get('version') == o['version'] and {'name': 'vidall:source-commit', 'value': o.get('commit') or 'NOASSERTION'} in c.get('properties', [])
            else:
                good = c.get('versionInfo') == o['version'] and c.get('licenseConcluded') == 'NOASSERTION'
            if not good:
                issues.append({'code': 'observed-' + kind + '-mismatch', 'component': name})
    return issues


def audit(lock, cdx, spdx, observed, root):
    issues = []

    def issue(code, component=None):
        issues.append({'code': code, 'component': component})

    def indexed(items):
        result = {}
        for item in items:
            name = item['name']
            if name in result:
                issue('duplicate-component', name)
            result[name] = item
        return result

    sources = lock['sources']
    if not sources:
        issue('empty-source-lock')
    cdx_items = indexed(cdx['components'])
    spdx_items = indexed(spdx['packages'])
    actual = indexed(observed['components'])
    for kind, items in [('cdx', cdx_items), ('spdx', spdx_items)]:
        if set(items) != set(sources):
            issue(kind + '-component-set-mismatch')
    rows = []
    for name, source in sources.items():
        c = cdx_items.get(name, {})
        s = spdx_items.get(name, {})
        cdx_ok = (c.get('version') == source['tag'] and
                  c.get('licenses') == [{'license': {'id': source['license']}}] and
                  {'type': 'vcs', 'url': source['repository'] + '@' + source['commit']} in c.get('externalReferences', []))
        spdx_ok = (s.get('versionInfo') == source['tag'] and
                   s.get('downloadLocation') == source['repository'] and
                   s.get('licenseDeclared') == source['license'] and
                   any(x.get('referenceType') == 'git' and x.get('referenceLocator') == source['commit'] for x in s.get('externalRefs', [])))
        if not cdx_ok:
            issue('cdx-lock-mismatch', name)
        if not spdx_ok:
            issue('spdx-lock-mismatch', name)
        o = actual.get(name)
        comparison = 'unverified'
        if not o:
            issue('locked-component-unverified', name)
        elif not o.get('commit'):
            issue('observed-revision-unverified', name)
        elif o['commit'] != source['commit']:
            comparison = 'mismatch'
            issue('observed-commit-mismatch', name)
        else:
            comparison = 'same-base-commit'
        rows.append({'name': name, 'lockedTag': source['tag'], 'lockedCommit': source['commit'],
                     'observedVersion': o.get('version') if o else None,
                     'observedCommit': o.get('commit') if o else None,
                     'revisionComparison': comparison, 'declaredSbomsMatchLock': cdx_ok and spdx_ok})
    records = observed.get('materials', [])
    materials = {m['path']: m for m in records}
    if len(materials) != len(records):
        issue('duplicate-material')
    for name, o in actual.items():
        if name not in sources:
            issue('observed-component-unlocked', name)
        if o.get('dirty'):
            issue('dirty-source-not-in-lock', name)
        if o.get('evidenceLevel') != 'source-rebuild-verified':
            issue('source-binding-unverified', name)
        if not o.get('licenseFiles') or any(p not in materials for p in o['licenseFiles']):
            issue('license-material-missing', name)
    for path, m in materials.items():
        try:
            p = (root / path).resolve()
            if Path(path).is_absolute() or not p.is_relative_to(root.resolve()):
                raise ValueError('材料路径超出项目')
            if not p.is_file():
                raise ValueError('材料必须是普通文件')
            digest = hashlib.sha256()
            with p.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != m['sha256']:
                raise ValueError('摘要不匹配')
        except (OSError, ValueError):
            issue('material-integrity-failed', path)
    for key, code in [('closureComplete', 'closure-incomplete'), ('sourceRebuildVerified', 'source-rebuild-unverified'), ('binaryBindingVerified', 'binary-binding-unverified')]:
        if observed.get(key) is not True:
            issue(code)
    tool_observation = observed.get('toolVersionObservation', {})
    if not isinstance(tool_observation, dict):
        issue('tool-version-observation-invalid')
    elif tool_observation.get('status') == 'mismatch':
        issue('tool-version-mismatch')
    return {'schemaVersion': 1, 'status': 'blocked' if issues else 'passed',
            'scope': 'SBOM 对锁文件的声明核对、缓存观察差异和归档材料完整性；不授予发布或真机验收。',
            'declaredSbomsMatchLock': all(r['declaredSbomsMatchLock'] for r in rows) and set(cdx_items) == set(spdx_items) == set(sources),
            'revisionMismatches': sum(r['revisionComparison'] == 'mismatch' for r in rows),
            'unverifiedLockedComponents': sum(r['revisionComparison'] == 'unverified' for r in rows),
            'materialCount': len(materials), 'comparisons': rows, 'issues': issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--declared-dir', type=Path, default=Path('release/audits/current-candidate'),
                        help='包含 sbom.cdx.json 和 sbom.spdx.json 的声明目录')
    parser.add_argument('--observed', default='release/audits/source-provenance/observed-sources.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    def read(path):
        value = json.loads((args.root / path).read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('输入 JSON 必须是对象')
        return value
    try:
        observed = read(args.observed)
        result = audit(read('native/config/sources.lock.json'), read(args.declared_dir / 'sbom.cdx.json'),
                       read(args.declared_dir / 'sbom.spdx.json'), observed, args.root)
        folder = Path(args.observed).parent
        sbom_issues = check_observed_sboms(observed, read(folder / 'observed-sbom.cdx.json'), read(folder / 'observed-sbom.spdx.json'))
        result['observedSbomsMatchEvidence'] = not sbom_issues
        result['issues'].extend(sbom_issues)
        if sbom_issues:
            result['status'] = 'blocked'
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'status': 'blocked', 'error': str(error)}
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        try:
            with args.output.open('x', encoding='utf-8') as report:
                report.write(output)
        except OSError as error:
            parser.error(f'无法创建新报告：{error}')
    else:
        print(output, end='')
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
