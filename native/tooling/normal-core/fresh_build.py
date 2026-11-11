#!/usr/bin/env python3
"""Fresh cross-root native build. Target ARM64 code is never executed.
Package PCs are explicitly relocated; produced binaries are never normalized.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shlex,shutil,subprocess,sys,time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'vendor'))
from input_gate import verify_files
from portable_elf import inventory,ar_members
from repro_gate import require_fresh
from path_policy import stable_install_plan,validate_target_config,macro_prefix_arg,require_no_root_bytes,ffmpeg_stage_path,validate_build_rpath
p=argparse.ArgumentParser()
for arg in ['input-root','run-root','sdk','meson','ninja','pkg-config']:p.add_argument('--'+arg,type=Path,required=True)
p.add_argument('--jobs',type=int,default=8)
p.add_argument('--stable-prefix',default=None,help='Stable target prefix; install isolated by DESTDIR. No binary normalization.')
p.add_argument('--ohcodec-experiment',action='store_true',help='Define MP_OHCODEC_LIFECYCLE_EXPERIMENT=1 for the mpv diagnostic build.')
p.add_argument('--ohcodec-diagnostic',action='store_true',help='Explicit diagnostic hooks and identity logging, independent of abort policy.')
p.add_argument('--test-return-replacement',action='store_true',help='Isolated test variant only; successful drain return replacement, no DIAGNOSTIC macro.')
p.add_argument('--handoff-trace',action='store_true')
p.add_argument('--handoff-test',action='store_true')
args=p.parse_args();PACKAGE=args.input_root.resolve();RUN=require_fresh(args.run_root);SDK=args.sdk.resolve();LLVM=SDK/'llvm/bin'
for name in ['meson','ninja','pkg_config']:setattr(args,name,getattr(args,name).absolute())
manifest=json.loads((PACKAGE/'package.json').read_text());records=[{'path':r['path'],'sizeBytes':r['size'],'sha256':r['sha256']} for r in manifest['files']]
verify_files(PACKAGE,records)
actual={x.relative_to(PACKAGE).as_posix() for x in PACKAGE.rglob('*') if x.is_file() or x.is_symlink()};assert actual=={r['path'] for r in records}|{'package.json'},'package has unlisted files'
for r in records:
 if r['path'].startswith('sources/') and (Path(r['path']).suffix in ['.o','.a','.so'] or any(part in ['.git','.build','meson-private'] for part in Path(r['path']).parts)):raise ValueError('compiled/build state in source package: '+r['path'])
RUN.mkdir(parents=True,exist_ok=False)
(RUN/'script-identity.json').write_text(json.dumps({'script':str(Path(__file__).resolve()),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'arguments':sys.argv[1:]},indent=2)+'\n')
for name in ['logs','tmp','host-cache','host-home','package-cache','build-tools']:(RUN/name).mkdir()
(RUN/'fresh-root.json').write_text(json.dumps({'runRoot':str(RUN),'freshRootVerified':True,'packageSHA256':hashlib.sha256((PACKAGE/'package.json').read_bytes()).hexdigest()},indent=2)+'\n')
FFMPEG=ffmpeg_stage_path(bool(args.stable_prefix))
for sub,dest in [('sources/mpv','mpv/source'),('sources/libplacebo','libplacebo/source'),('deps','deps'),('ffmpeg',FFMPEG)]:
 shutil.copytree(PACKAGE/sub,RUN/dest,symlinks=False)
 subset=[{'path':r['path'][len(sub)+1:],'sizeBytes':r['sizeBytes'],'sha256':r['sha256']} for r in records if r['path'].startswith(sub+'/')];verify_files(RUN/dest,subset,exact=True)
relocations=[]
for folder in [Path('deps'),FFMPEG]:
 for pc in sorted((RUN/folder).rglob('*.pc')):
  original=pc.read_bytes();text=original.decode()
  for rel in manifest['relocations']:text=text.replace(rel['from'],str(RUN/(FFMPEG if rel['to']=='ffmpeg' else rel['to'])))
  if text.encode()!=original:pc.write_text(text)
  if '/.cache/' in text or '/out/phase16/' in text:raise ValueError('PC retained old/cache absolute path: '+str(pc))
  relocations.append({'path':str(pc.relative_to(RUN)),'beforeSHA256':hashlib.sha256(original).hexdigest(),'afterSHA256':hashlib.sha256(pc.read_bytes()).hexdigest()})
(RUN/'pc-relocations.json').write_text(json.dumps(relocations,indent=2)+'\n')
basepaths=[str(args.ninja.parent),str(args.meson.parent),str(Path(sys.executable).parent),str(LLVM),str(args.pkg_config.parent),'/usr/bin','/bin','/usr/sbin','/sbin']
env={'HOME':str(RUN/'host-home'),'PATH':os.pathsep.join(dict.fromkeys(basepaths)),'LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','CCACHE_DISABLE':'1','PKG_CONFIG':str(args.pkg_config),'TMPDIR':str(RUN/'tmp'),'XDG_CACHE_HOME':str(RUN/'host-cache'),'MESON_PACKAGE_CACHE_DIR':str(RUN/'package-cache'),'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,'NINJA_STATUS':'[%f/%t] '}
commands=[]
def run(name,argv,stage_env=None,cwd=RUN):
 log=RUN/'logs'/(name+'.log');start=time.time()
 with log.open('w') as stream:proc=subprocess.run([str(a) for a in argv],cwd=cwd,env=stage_env or env,stdout=stream,stderr=subprocess.STDOUT)
 row={'name':name,'argv':[str(a) for a in argv],'cwd':str(cwd),'environment':dict(stage_env or env),'returncode':proc.returncode,'elapsedSeconds':time.time()-start,'log':str(log.relative_to(RUN))};commands.append(row);(RUN/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if proc.returncode:raise RuntimeError(name+' failed: '+str(log))
 return log.read_text()

tools={}
for name,path in [('meson',args.meson),('ninja',args.ninja),('pkg-config',args.pkg_config),('python',Path(sys.executable)),('clang',LLVM/'clang'),('clang++',LLVM/'clang++'),('ld.lld',LLVM/'ld.lld'),('llvm-ar',LLVM/'llvm-ar'),('llvm-strip',LLVM/'llvm-strip'),('llvm-readelf',LLVM/'llvm-readelf'),('llvm-objdump',LLVM/'llvm-objdump')]:
 raw=path.read_bytes();tools[name]={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
 if name in ['meson','ninja','pkg-config','python','clang']:run('tool-'+name,[path,'--version'])
(RUN/'tools.json').write_text(json.dumps(tools,indent=2)+'\n')
base_options={'target':'aarch64-linux-ohos','buildtype':'release','default_library':'static','wrap_mode':'nodownload','c_args':['--target=aarch64-linux-ohos','--sysroot='+str(SDK/'sysroot'),'-fPIC','-D__MUSL__=1','-Wno-int-conversion'],'link_args':['--target=aarch64-linux-ohos','-fuse-ld=lld','-lc++_shared']}
for stage in ['libplacebo','mpv']:
 c_args=base_options['c_args']+([macro_prefix_arg(RUN)] if args.stable_prefix and stage=='mpv' else [])
 if args.handoff_test and stage=='mpv':
  c_args=c_args+['-DMP_OHCODEC_HANDOFF_TEST=1']
 if args.handoff_trace and stage=='mpv':
  c_args=c_args+['-DMP_OHCODEC_HANDOFF_TRACE=1']
 if args.ohcodec_experiment and stage=='mpv':
  c_args=c_args+['-DMP_OHCODEC_LIFECYCLE_EXPERIMENT=1']
 if args.test_return_replacement and stage=='mpv':
  c_args=c_args+['-DMP_OHCODEC_TEST_RETURN_REPLACEMENT=1']
 if args.ohcodec_diagnostic and stage=='mpv':
  c_args=c_args+['-DMP_OHCODEC_DIAGNOSTIC=1']
 link=base_options['link_args']+(['-Wl,-Map,'+str(RUN/'mpv/link.map'),'-Wl,--trace'] if stage=='mpv' else [])
 text="[host_machine]\nsystem = 'linux'\ncpu_family = 'aarch64'\ncpu = 'arm64-v8a'\nendian = 'little'\n\n[binaries]\n"
 for key,value in {'c':LLVM/'clang','cpp':LLVM/'clang++','ar':LLVM/'llvm-ar','strip':LLVM/'llvm-strip','c_ld':LLVM/'ld.lld','cpp_ld':LLVM/'ld.lld','pkg-config':args.pkg_config}.items():text+=key+' = '+repr(str(value))+'\n'
 text+='\n[built-in options]\n'
 for key,value in {'c_args':c_args,'cpp_args':c_args,'c_link_args':link,'cpp_link_args':link,'buildtype':'release','default_library':'static','wrap_mode':'nodownload'}.items():text+=key+' = '+repr(value)+'\n'
 (RUN/'build-tools'/(stage+'.ini')).write_text(text)
pl_options=['-Ddovi=enabled','-Dlibdovi=enabled','-Dlcms=enabled','-Dshaderc=enabled','-Dvulkan=enabled','-Dopengl=enabled','-Ddemos=false','-Dtests=false','-Dbench=false']
mpv_options=['--default-library=shared','-Dstrip=false','-Dopensles=disabled','-Dohos=enabled','-Degl-ohos=enabled','-Dvulkan=enabled','-Dshaderc=enabled','-Dlua=enabled','-Dgpl=true','-Dbuild-date=false','-Dcplayer=false','-Dmanpage-build=disabled']
plenv={**env,'PKG_CONFIG_PATH':str(RUN/'deps/lib/pkgconfig'),'PKG_CONFIG_LIBDIR':str(RUN/'deps/lib/pkgconfig'),'GIT_CEILING_DIRECTORIES':str(RUN/'libplacebo')}
run('libplacebo-setup',[args.meson,'setup',RUN/'libplacebo/build',RUN/'libplacebo/source','--cross-file',RUN/'build-tools/libplacebo.ini','--prefix',RUN/'libplacebo/install',*pl_options],plenv)
run('libplacebo-build',[args.ninja,'-C',RUN/'libplacebo/build','-v','-j'+str(args.jobs)],plenv)
run('libplacebo-deps',[args.ninja,'-C',RUN/'libplacebo/build','-t','deps'],plenv)
run('libplacebo-install',[args.meson,'install','-C',RUN/'libplacebo/build','--no-rebuild'],plenv)
pcpath=os.pathsep.join(str(RUN/x) for x in [Path('libplacebo/install/lib/pkgconfig'),FFMPEG/'lib/pkgconfig',Path('deps/lib/pkgconfig')]);mpvenv={**env,'PKG_CONFIG_PATH':pcpath,'PKG_CONFIG_LIBDIR':pcpath,'GIT_CEILING_DIRECTORIES':str(RUN/'mpv')}
plan=stable_install_plan(RUN,args.stable_prefix) if args.stable_prefix else {'setupArgs':['--cross-file',str(RUN/'build-tools/mpv.ini'),'--prefix='+str(RUN/'install')],'destdir':None,'artifact':RUN/'install/lib/libmpv.so'}
(RUN/'build-profile.json').write_text(json.dumps({'profile':'stable-target-prefix-macro-map-origin-staging' if args.stable_prefix else 'phase16-per-run-prefix','stablePrefix':args.stable_prefix,'ffmpegRelative':FFMPEG.as_posix(),'artifact':str(plan['artifact']),'ohcodecLifecycleExperiment':bool(args.ohcodec_experiment),'ohcodecDiagnostic':bool(args.ohcodec_diagnostic),'testReturnReplacement':bool(args.test_return_replacement),'handoffTrace':bool(args.handoff_trace),'handoffTest':bool(args.handoff_test)},indent=2)+'\n')
run('mpv-setup',[args.meson,'setup',RUN/'mpv/build',RUN/'mpv/source',*plan['setupArgs'],*mpv_options],mpvenv)
if args.stable_prefix:
 validate_target_config((RUN/'mpv/build/config.h').read_text(),RUN,args.stable_prefix)
 (RUN/'target-path-gate.json').write_text(json.dumps({'passed':True,'prefix':args.stable_prefix,'crossFileArgument':'build-tools/mpv.ini','noRunRootInConfigurationOrConfdir':True},indent=2)+'\n')
commandtext=run('mpv-commands',[args.ninja,'-C',RUN/'mpv/build','-t','commands'],mpvenv)
linklines=[line for line in commandtext.splitlines() if ' -shared ' in line and ' -o libmpv.so ' in line];assert len(linklines)==1,linklines
(RUN/'logs/mpv-link-command.txt').write_text(linklines[0]+'\n')
if args.stable_prefix:
 validate_build_rpath(linklines[0],RUN)
 (RUN/'build-rpath-gate.json').write_text(json.dumps({'passed':True,'expectedOriginRelativeDirectory':'../source/_staged/ffmpeg/lib','ffmpegRelative':FFMPEG.as_posix(),'binaryPatched':False},indent=2)+'\n')
run('mpv-build',[args.ninja,'-C',RUN/'mpv/build','-v','-j'+str(args.jobs)],mpvenv)
run('mpv-deps',[args.ninja,'-C',RUN/'mpv/build','-t','deps'],mpvenv)
installenv={**mpvenv,'DESTDIR':str(plan['destdir'])} if plan['destdir'] else mpvenv
run('mpv-install',[args.meson,'install','-C',RUN/'mpv/build','--no-rebuild'],installenv)
artifact=plan['artifact'];assert artifact.is_file();shutil.copy2(artifact,RUN/'mpv/install-unstripped.so');run('mpv-strip',[LLVM/'llvm-strip',artifact],mpvenv)
run('static-validation',[sys.executable,'-B',HERE/'validate_one.py','--artifact',artifact,'--symbols',RUN/'mpv/install-unstripped.so','--build',RUN/'mpv/build','--source',RUN/'mpv/source','--map',RUN/'mpv/link.map','--ffmpeg-lib',RUN/FFMPEG/'lib','--link-command',RUN/'logs/mpv-link-command.txt','--evidence-root',RUN/'validation','--input-root',PACKAGE,'--sdk',SDK],mpvenv)
if args.stable_prefix:
 from portable_elf import Binary
 final=Binary(artifact);parts=[final.at(sec['address'],sec['size']) for sec in final.inventory['sections'].values() if sec['allocated'] and sec['type']!=8 and sec['size']]
 require_no_root_bytes(parts,RUN)
 (RUN/'allocated-path-gate.json').write_text(json.dumps({'passed':True,'compilerMacroMap':macro_prefix_arg(RUN),'allocatedPartsChecked':len(parts),'binaryPatched':False},indent=2)+'\n')
run('collect-evidence',[sys.executable,'-B',HERE/'collect_run.py','--run-root',RUN,'--input-root',PACKAGE,'--sdk',SDK],mpvenv)
print((RUN/'logs/collect-evidence.log').read_text())
