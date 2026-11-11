"""Separate stable target paths from per-run staging; never edit binaries."""
from pathlib import Path
import json,re,shlex,posixpath

def stable_install_plan(run_root,prefix='/usr/local'):
    run_root=Path(run_root).resolve();target=Path(prefix)
    if not target.is_absolute() or '..' in target.parts or target.is_relative_to(run_root):raise ValueError('target prefix must be stable and outside build root')
    return {'setupArgs':['--cross-file','build-tools/mpv.ini','--prefix='+str(target)],'destdir':run_root/'install','artifact':run_root/'install'/str(target).lstrip('/')/'lib/libmpv.so'}

def validate_target_config(text,run_root,prefix='/usr/local'):
    found={}
    for name,value in re.findall(r'^#define\s+(CONFIGURATION|MPV_CONFDIR)\s+("(?:[^"\\]|\\.)*")\s*$',text,re.M):
        if name in found:raise ValueError('duplicate generated path macro')
        found[name]=json.loads(value)
    if set(found)!={'CONFIGURATION','MPV_CONFDIR'}:raise ValueError('missing generated path macros')
    if str(Path(run_root).resolve()) in '\n'.join(found.values()):raise ValueError('run root leaked into target configuration')
    if re.search(r'--cross-file=/',found['CONFIGURATION']):raise ValueError('absolute crossfile embedded')
    if '--cross-file=build-tools/mpv.ini' not in found['CONFIGURATION'] or '-Dprefix='+prefix not in found['CONFIGURATION']:raise ValueError('wrong stable configuration')
    if found['MPV_CONFDIR']!=str(Path(prefix)/'etc/mpv'):raise ValueError('wrong target confdir')
    return True

def macro_prefix_arg(run_root):
    root=str(Path(run_root).resolve())
    if '=' in root:raise ValueError('ambiguous macro-prefix-map root')
    return '-fmacro-prefix-map='+root+'=.'

def require_no_root_bytes(allocated_parts,run_root):
    if not allocated_parts or not any(allocated_parts):raise ValueError('missing allocated-byte evidence')
    needle=str(Path(run_root).resolve()).encode()
    for index,data in enumerate(allocated_parts):
        if needle in data:raise ValueError('run root retained in allocated part '+str(index)+' at '+str(data.index(needle)))
    return True

def ffmpeg_stage_path(stable):
    return Path('mpv/source/_staged/ffmpeg' if stable else 'ffmpeg')

def validate_build_rpath(command,run_root):
    paths=[]
    for arg in shlex.split(command):
        if arg.startswith(('-Wl,-rpath,','-Wl,-rpath=')):paths.append(arg[11:])
    if len(paths)!=1:raise ValueError('expected exactly one automatic build rpath')
    path=paths[0]
    if not path.startswith('$ORIGIN/') or posixpath.normpath(path[len('$ORIGIN/'):])!='../source/_staged/ffmpeg/lib':raise ValueError('build rpath must resolve to declared source-subtree dependency')
    if str(Path(run_root).resolve()) in path:raise ValueError('absolute run root in build rpath')
    return True

def require_no_runtime_paths(paths):
    if paths:raise ValueError('installed artifact retained RPATH or RUNPATH')
    return True
