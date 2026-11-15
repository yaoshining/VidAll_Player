"""Fail-closed cross-root reproducibility checks; no output normalization."""
from pathlib import Path

FIELDS=('configuration','linkInputs','artifactHashes','allocatedSections','exports','imports','features','archiveMembers')

def require_fresh(path):
    path=Path(path).absolute()
    if path.exists() or path.is_symlink():raise ValueError('run root already exists; refuse reuse')
    return path.resolve()

def compare_runs(a,b):
    for row in (a,b):
        if row.get('freshRootVerified') is not True:raise ValueError('missing fresh-root evidence')
        if not isinstance(row.get('runRoot'),str) or not Path(row['runRoot']).is_absolute():raise ValueError('missing absolute run root')
        for field in FIELDS:
            if field not in row:raise ValueError('missing comparison evidence: '+field)
    if Path(a['runRoot']).resolve()==Path(b['runRoot']).resolve():raise ValueError('comparison requires distinct roots')
    different=[field for field in FIELDS if a[field]!=b[field]]
    return {'passed':not different,'differentFields':different,'normalizationAppliedToArtifacts':False,'runtimeAcceptance':False}
