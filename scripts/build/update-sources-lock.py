#!/usr/bin/env python3
"""验证并更新补丁摘要；不生成任何占位供应链输入。"""
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / 'native/config/sources.lock.json'
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
COMMIT_RE = re.compile(r'^[0-9a-f]{40}$')

def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    for name, source in lock.get('sources', {}).items():
        if 'example.invalid' in source.get('repository', '') or not COMMIT_RE.fullmatch(source.get('commit', '')) or set(source['commit']) == {'0'}:
            raise SystemExit(f'拒绝写入未锁定来源: {name}')
        if source.get('fetchMethod') == 'archive':
            value = source.get('archiveSha256', '')
            if not SHA256_RE.fullmatch(value) or set(value) == {'0'} or not source.get('archiveUrl'):
                raise SystemExit(f'拒绝写入缺少可信归档摘要的来源: {name}')
    for tool, details in lock.get('tools', {}).items():
        value = details.get('sha256', '')
        digests = details.get('digests', {})
        if not ((SHA256_RE.fullmatch(value) and set(value) != {'0'}) or (digests and all(SHA256_RE.fullmatch(v) and set(v) != {'0'} for v in digests.values()))):
            raise SystemExit(f'拒绝写入缺少可信工具摘要的工具: {tool}')
    for patch in lock.get('patches', []):
        path = ROOT / patch['path']
        if not path.is_file():
            raise SystemExit(f'补丁不存在: {path}')
        patch['sha256'] = digest(path)
    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'已验证并更新 {LOCK_PATH}')

if __name__ == '__main__':
    main()
