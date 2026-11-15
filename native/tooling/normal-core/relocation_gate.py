from pathlib import Path
import hashlib

def relocated_records(root, records, relocations, prefix, source_root, replacements):
    root=Path(root);expected={r['path'] for r in records}
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=expected:raise ValueError('external input file set differs')
    declared={}
    for r in relocations:
        if not r['path'].startswith(prefix+'/'):continue
        name=r['path'][len(prefix)+1:]
        if name in declared or name not in expected or not name.startswith('lib/pkgconfig/') or not name.endswith('.pc'):raise ValueError('invalid relocation declaration')
        declared[name]=r
    result=[]
    for row in records:
        raw=(root/row['path']).read_bytes();digest=hashlib.sha256(raw).hexdigest();target=dict(row)
        original=(Path(source_root)/row['path']).read_bytes()
        if len(original)!=row['sizeBytes'] or hashlib.sha256(original).hexdigest()!=row['sha256']:raise ValueError('original input changed')
        if row['path'] in declared:
            rel=declared[row['path']]
            if rel['beforeSHA256']!=row['sha256'] or rel['afterSHA256']!=digest:raise ValueError('relocation before/after identity differs')
            expected=original.decode('utf-8')
            for before,after in replacements:expected=expected.replace(before,after)
            if expected.encode('utf-8')!=raw:raise ValueError('undeclared pc content transformation')
            target.update(sizeBytes=len(raw),sha256=digest)
        elif len(raw)!=row['sizeBytes'] or digest!=row['sha256']:raise ValueError('undeclared input change')
        result.append(target)
    return result
