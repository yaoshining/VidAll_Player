#!/usr/bin/env python3
"""从封存对应源码交叉构建 x86 Player 核心；仅消费上游 FFmpeg SDK。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'release/inputs/018-x86-core'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(archive, target):
    with tarfile.open(archive) as tar:
        for item in tar.getmembers():
            for name in [item.name, item.linkname]:
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('源码归档路径越界')
            if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                raise ValueError('源码归档含特殊文件')
        tar.extractall(target)

def build(args):
    lock = json.loads((INPUT/'source-lock.json').read_text())
    if sha(INPUT/'player-sources.tar.gz') != lock['sourceArchiveSHA256']:
        raise ValueError('对应源码包摘要错误')
    if sha(INPUT/'source-files.json') != lock['sourceFilesSHA256']:
        raise ValueError('源码文件清单摘要错误')
    patch = ROOT/'native/patches/phase30/0016-optional-ohcodec-software-build.patch'
    if sha(patch) != lock['patchSHA256']:
        raise ValueError('软件解码补丁摘要错误')
    ffmpeg = args.ffmpeg_sdk.resolve()
    if sha(ffmpeg/'manifest.json') != lock['ffmpegSdkManifestSHA256']:
        raise ValueError('FFmpeg SDK 身份错误')
    for row in json.loads((ffmpeg/'manifest.json').read_text())['files']:
        if sha(ffmpeg/row['path']) != row['sha256']:
            raise ValueError('FFmpeg SDK 文件漂移')
    run = args.out.resolve()
    run.mkdir(parents=True, exist_ok=False)
    source = run/'input';source.mkdir()
    extract(INPUT/'player-sources.tar.gz', source)
    for row in json.loads((INPUT/'source-files.json').read_text()):
        if sha(source/row['path']) != row['sha256']:
            raise ValueError('源码文件漂移：'+row['path'])
    sdk = args.sdk.resolve();llvm = sdk/'llvm/bin';prefix = run/'deps'
    logs = run/'logs';logs.mkdir()
    env = {'PATH':os.pathsep.join([str(args.meson.parent), str(args.ninja.parent),
           str(args.pkg_config.parent), str(llvm), '/usr/bin', '/bin']),
           'TMPDIR':str(run/'tmp'), 'LANG':'C', 'LC_ALL':'C',
           'PKG_CONFIG_LIBDIR':str(prefix/'lib/pkgconfig'),
           'PKG_CONFIG_PATH':str(prefix/'lib/pkgconfig'), 'CCACHE_DISABLE':'1'}
    if 'HOME' in os.environ:
        env['HOME'] = os.environ['HOME']
    (run/'tmp').mkdir()
    commands = []
    def command(name, argv, cwd=run, extra=None):
        print(name, flush=True)
        with (logs/(name+'.log')).open('w') as output:
            result = subprocess.run([str(a) for a in argv], cwd=cwd,
                       env={**env, **(extra or {})}, stdout=output, stderr=subprocess.STDOUT)
        commands.append({'name':name, 'argv':[str(a) for a in argv],
                         'cwd':str(cwd), 'returncode':result.returncode})
        (run/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        if result.returncode:
            raise RuntimeError(name+' 失败，见 '+str(logs/(name+'.log')))
    tools = {name:{'path':str(path),'sha256':sha(path)} for name,path in
             [('meson',args.meson),('ninja',args.ninja),('pkg-config',args.pkg_config),
              ('clang',llvm/'clang'),('clang++',llvm/'clang++'),('ar',llvm/'llvm-ar'),
              ('strip',llvm/'llvm-strip'),('ld',llvm/'ld.lld')]}
    (run/'tools.json').write_text(json.dumps(tools,indent=2)+'\n')
    command('mpv-patch',['git','apply','--directory=sources/mpv',str(patch)],source)
    cargs = ['--target=x86_64-linux-ohos','--sysroot='+str(sdk/'sysroot'),'-fPIC','-D__MUSL__=1',
             '-ffile-prefix-map='+str(run)+'=/vidall-player/build']
    link = ['--target=x86_64-linux-ohos','-fuse-ld=lld','-lc++_shared']
    cross = run/'cross.ini'
    cross.write_text("[host_machine]\nsystem = 'linux'\ncpu_family = 'x86_64'\ncpu = 'x86_64'\nendian = 'little'\n[binaries]\n"+
        ''.join(k+' = '+repr(str(v))+'\n' for k,v in {'c':llvm/'clang','cpp':llvm/'clang++',
        'ar':llvm/'llvm-ar','strip':llvm/'llvm-strip','pkg-config':args.pkg_config}.items())+
        '[built-in options]\n'+''.join(k+' = '+repr(v)+'\n' for k,v in
        {'c_args':cargs,'cpp_args':cargs,'c_link_args':link,'cpp_link_args':link}.items())+
        '[properties]\nneeds_exe_wrapper = true\n')
    def meson_build(name, src, options, shared=False):
        folder = run/(name+'-build')
        command(name+'-setup',[args.meson,'setup',folder,src,'--cross-file',cross,
                '--prefix', '/vidall-player' if shared else prefix, '--libdir=lib',
                '--default-library='+('shared' if shared else 'static'),'--buildtype=release',
                '--wrap-mode=nodownload','-Dauto_features=disabled',*options])
        command(name+'-build',[args.ninja,'-C',folder,'-j'+str(args.jobs)])
        command(name+'-install',[args.meson,'install','-C',folder,'--no-rebuild'],
                extra={'DESTDIR':str(run/'stage')} if shared else None)
    for name,options in [
        ('freetype',['-Dzlib=internal','-Dbrotli=disabled','-Dbzip2=disabled','-Dpng=disabled','-Dharfbuzz=disabled']),
        ('harfbuzz',['-Dfreetype=enabled','-Dglib=disabled','-Dgobject=disabled','-Dcairo=disabled',
                    '-Dicu=disabled','-Dtests=disabled','-Dutilities=disabled','-Ddocs=disabled','-Dintrospection=disabled']),
        ('fribidi',['-Ddocs=false','-Dbin=false','-Dtests=false']),
        ('libass',['-Dfontconfig=disabled','-Drequire-system-font-provider=false','-Dasm=disabled'])]:
        folder = run/name;folder.mkdir();extract(source/'dependencies'/(name+'.tar.gz'),folder)
        meson_build(name,next(folder.iterdir()),options)
    lua = run/'lua';lua.mkdir();extract(source/'dependencies/lua.tar.gz',lua)
    lua = next(lua.iterdir())/'src';objects = run/'lua-objects';objects.mkdir()
    for path in sorted(lua.glob('*.c')):
        if path.name not in ['lua.c','luac.c']:
            command('lua-'+path.stem,[llvm/'clang',*cargs,'-O2','-DLUA_USE_POSIX',
                    '-DLUA_USE_DLOPEN','-c',path,'-o',objects/(path.stem+'.o')])
    command('lua-archive',[llvm/'llvm-ar','rcs',prefix/'lib/liblua.a',*sorted(objects.glob('*.o'))])
    for name in ['lua.h','luaconf.h','lualib.h','lauxlib.h']:
        shutil.copyfile(lua/name,prefix/'include'/name)
    (prefix/'lib/pkgconfig/lua.pc').write_text('prefix='+str(prefix)+'\nlibdir=${prefix}/lib\nincludedir=${prefix}/include\nName: Lua\nDescription: Lua\nVersion: 5.2.4\nLibs: -L${libdir} -llua -lm -ldl\nCflags: -I${includedir}\n')
    meson_build('libplacebo',source/'sources/libplacebo',['-Dopengl=enabled','-Dgl-proc-addr=enabled',
                '-Ddemos=false','-Dtests=false','-Dbench=false'])
    env['PKG_CONFIG_PATH']=env['PKG_CONFIG_LIBDIR']=os.pathsep.join([str(prefix/'lib/pkgconfig'),str(ffmpeg/'lib/pkgconfig')])
    strict = link+['-Wl,--no-allow-shlib-undefined','-Wl,-rpath-link,'+str(ffmpeg/'lib'),
                   '-Wl,-Map,'+str(run/'mpv.map')]
    meson_build('mpv',source/'sources/mpv',['-Dohos=enabled','-Dohcodec=disabled',
                '-Dgl=enabled','-Degl-ohos=enabled','-Dvulkan=disabled','-Dlua=enabled',
                '-Dcplayer=false','-Dbuild-date=false','-Dmanpage-build=disabled',
                '-Db_lundef=true','-Dc_link_args='+repr(strict)],shared=True)
    core = run/'stage/vidall-player/lib/libmpv.so';symbols = run/'libmpv.symbols.so'
    shutil.copyfile(core,symbols)
    command('strip',[llvm/'llvm-strip','--strip-all',core])
    (run/'result.json').write_text(json.dumps({'passed':True,'architecture':'x86_64',
        'artifact':str(core),'sha256':sha(core),'symbolCompanionSHA256':sha(symbols),
        'sourceArchiveSHA256':lock['sourceArchiveSHA256'],'scriptSHA256':sha(Path(__file__)),
        'ffmpegSdkManifestSHA256':lock['ffmpegSdkManifestSHA256'],'targetExecuted':False},indent=2)+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['out','ffmpeg-sdk','sdk','meson','ninja','pkg-config']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=8)
    build(parser.parse_args())
