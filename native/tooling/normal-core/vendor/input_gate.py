"""Verify exact staged inputs; digest pairing is provenance, not ABI equivalence."""
from pathlib import Path
import hashlib

def verify_files(root,records,exact=False):
    root=Path(root)
    if not records:raise ValueError('empty input manifest')
    names=set()
    for row in records:
        rel=Path(row['path'])
        if rel.is_absolute()or '..'in rel.parts or not rel.parts:raise ValueError('unsafe input path')
        name=rel.as_posix()
        if name in names:raise ValueError('duplicate manifest path')
        names.add(name)
        p=root/rel
        for depth in range(1,len(rel.parts)+1):
            if root.joinpath(*rel.parts[:depth]).is_symlink():raise ValueError('symlink input not allowed in staged tree')
        if not p.is_file():raise FileNotFoundError(str(p))
        data=p.read_bytes()
        if len(data)!=row['sizeBytes']or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('input content differs: '+name)
    if exact:
        actual={p.relative_to(root).as_posix()for p in root.rglob('*')if p.is_file()or p.is_symlink()}
        if actual!=names:raise ValueError('unexpected or missing input files: '+str(sorted(actual^names)))
    return True
