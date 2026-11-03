#!/usr/bin/env python3
"""只读原包，在新目录准备私有归档候选；不访问网络。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from urllib.parse import urlsplit

CHUNK = 2097152000
LIMIT = 2147483648
MANIFEST = 'deveco26-archive-manifest.json'
BLOCK = 1024 * 1024
LOCK = Path(__file__).resolve().parent.parent/'deveco26/archive-lock.json'


def layout(size, chunk):
    if type(size) is not int or type(chunk) is not int or size <= 0 or not 0 < chunk < LIMIT:
        raise ValueError('尺寸或分片上限不符')
    return [min(chunk, size-offset) for offset in range(0, size, chunk)]


def safe_path(path):
    path = Path(path)
    if '..' in path.parts:
        raise ValueError('拒绝路径逃逸')
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError('拒绝符号链接路径')
    return path


def ordinary_file(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('要求普通文件')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('要求普通文件')
    return info


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def digest_valid(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def archive_identity(lock, chunk):
    archive = lock['archive']
    layout(archive['bytes'], chunk)
    url = urlsplit(archive['urlWithoutQuery'])
    if not digest_valid(archive['sha256']) or url.scheme != 'https' or not url.netloc or url.query or url.fragment or url.username or url.password:
        raise ValueError('可信归档锁身份不符')
    if lock.get('formalArtifactAllowed') is not False:
        raise ValueError('不是非发布资产准备锁')
    return dict(archive)


def write_piece(src, dest, size, whole):
    digest = hashlib.sha256()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(dest, flags, 0o600), 'wb') as output:
        remaining = size
        while remaining:
            data = src.read(min(BLOCK, remaining))
            if not data:
                raise ValueError('原包截断')
            output.write(data)
            digest.update(data)
            whole.update(data)
            remaining -= len(data)
    return digest.hexdigest()


def prepare(source, out, lock, chunk=CHUNK):
    archive = archive_identity(lock, chunk)
    source, out = safe_path(source), safe_path(out)
    before = ordinary_file(source)
    if before.st_size != archive['bytes']:
        raise ValueError('原包大小不符')
    if not out.parent.is_dir():
        raise ValueError('输出父目录不存在')
    if shutil.disk_usage(out.parent).free < archive['bytes'] + 1024*1024:
        raise ValueError('本地分片空间不足')
    # mkdir 必须独占成功；其前拒绝条件均不能清理已有目录。
    out.mkdir(mode=0o700)
    owned = out.stat()
    try:
        rows, offset, whole = [], 0, hashlib.sha256()
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as src:
            if identity(os.fstat(src.fileno())) != identity(before):
                raise ValueError('输入身份在打开前变化')
            for ordinal, size in enumerate(layout(archive['bytes'], chunk), 1):
                name = f'studio26.zip.part{ordinal:03d}'
                digest = write_piece(src, out/name, size, whole)
                rows.append(dict(ordinal=ordinal, name=name, offset=offset, bytes=size, sha256=digest))
                offset += size
            if src.read(1) or whole.hexdigest() != archive['sha256']:
                raise ValueError('原包完整摘要或长度不符')
            if identity(os.fstat(src.fileno())) != identity(before) or identity(ordinary_file(source)) != identity(before):
                raise ValueError('读取时原包发生变化')
        result = dict(schemaVersion=1, archive=archive, chunkBytes=chunk, parts=rows, formalArtifactAllowed=False)
        content = (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode()
        with os.fdopen(os.open(out/MANIFEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
            f.write(content)
        return result
    except BaseException:
        # 仅删除本次独占建立且仍是同 inode 的目录；从不清理调用前已有目录。
        if out.is_symlink() or not out.is_dir() or (out.stat().st_dev, out.stat().st_ino) != (owned.st_dev, owned.st_ino):
            raise ValueError('输出目录身份变化；拒绝自动清理')
        shutil.rmtree(out)
        raise


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('重复JSON键')
        result[key] = value
    return result


def verify(out, lock, chunk=CHUNK):
    archive = archive_identity(lock, chunk)
    out = safe_path(out)
    path = out/MANIFEST
    info = ordinary_file(path)
    if info.st_size > 65536:
        raise ValueError('清单异常过大')
    raw = path.read_bytes()
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    snapshots = {path: identity(info)}
    keys = {'schemaVersion','archive','chunkBytes','parts','formalArtifactAllowed'}
    if not isinstance(manifest, dict) or set(manifest) != keys or type(manifest['schemaVersion']) is not int or manifest['schemaVersion'] != 1 or manifest['formalArtifactAllowed'] is not False:
        raise ValueError('清单schema不符')
    if manifest['archive'] != archive or type(manifest['chunkBytes']) is not int or manifest['chunkBytes'] != chunk:
        raise ValueError('清单不能重新定义可信归档或分片身份')
    sizes = layout(archive['bytes'], chunk)
    rows = manifest['parts']
    if not isinstance(rows, list) or len(rows) != len(sizes):
        raise ValueError('分片集合不符')
    names = {MANIFEST} | {f'studio26.zip.part{i:03d}' for i in range(1, len(sizes)+1)}
    if {x.name for x in out.iterdir()} != names:
        raise ValueError('目录存在缺失或额外产物')
    whole, offset = hashlib.sha256(), 0
    for ordinal, (size, row) in enumerate(zip(sizes, rows), 1):
        expected = dict(ordinal=ordinal, name=f'studio26.zip.part{ordinal:03d}', offset=offset, bytes=size)
        if not isinstance(row, dict) or set(row) != set(expected) | {'sha256'} or not digest_valid(row['sha256']):
            raise ValueError('分片字段不符')
        if any(row[k] != v or type(row[k]) is not type(v) for k,v in expected.items()):
            raise ValueError('分片布局或顺序不符')
        part = out/row['name']
        before = ordinary_file(part)
        snapshots[part] = identity(before)
        if before.st_size != size:
            raise ValueError('分片大小不符')
        digest, count = hashlib.sha256(), 0
        with os.fdopen(os.open(part, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
            while data := f.read(BLOCK):
                count += len(data)
                if count > size:
                    raise ValueError('分片超长')
                digest.update(data);whole.update(data)
            if identity(os.fstat(f.fileno())) != identity(before):
                raise ValueError('分片读取中变化')
        if count != size or digest.hexdigest() != row['sha256']:
            raise ValueError('分片摘要不符')
        offset += size
    if whole.hexdigest() != archive['sha256']:
        raise ValueError('拼接完整摘要不符')
    if any(identity(ordinary_file(p)) != expected for p, expected in snapshots.items()) or path.read_bytes() != raw:
        raise ValueError('验证期间目录内容被替换')
    if {x.name for x in out.iterdir()} != names:
        raise ValueError('验证期间产物集合发生变化')
    return dict(passed=True, archiveSHA256=whole.hexdigest(), archiveBytes=offset, parts=len(rows), manifestSHA256=hashlib.sha256(raw).hexdigest(), formalArtifactAllowed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare','verify'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        lock = json.loads(LOCK.read_text())
        if args.mode == 'prepare':
            if args.source is None:
                raise ValueError('prepare缺少原包')
            prepare(args.source,args.out,lock)
        result = verify(args.out,lock)
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception as e:
        # 不把输入路径/任意异常内容发布到证据。
        print(json.dumps({'passed':False,'errorType':type(e).__name__,'formalArtifactAllowed':False}));return 1

if __name__ == '__main__':sys.exit(main())
