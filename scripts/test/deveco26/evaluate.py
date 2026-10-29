#!/usr/bin/env python3
"""独立26评估：不修改旧锁、产品API配置或固定八库。"""
import shlex,subprocess,argparse,hashlib,importlib.util,json,os,platform,re,sys,tarfile,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load(name):
 p=HERE.parent/'normal-core'/(name+'.py');s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
TARGET=load('ci-target');CONTEXT=load('ci-context')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def hash_valid(h):return isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) is not None
def verify_file(p,size,digest):
 if not hash_valid(digest) or not Path(p).is_file() or Path(p).stat().st_size!=size or sha(p)!=digest:raise ValueError('输入大小/摘要缺失或不匹配')
def response_identity(status,headers,size,byte_range=None):
 if byte_range is None:
  if status!=200 or int(headers.get('Content-Length','-1'))!=size:raise ValueError('完整GET状态/长度错误')
 else:
  a,b=byte_range
  if status!=206 or headers.get('Content-Range')!=f'bytes {a}-{b}/{size}' or int(headers.get('Content-Length','-1'))!=b-a+1:raise ValueError('Range状态/范围错误')
def preflight(studio,wrapper,common,lock,machine):
 if machine!=lock['architecture']:raise ValueError('宿主架构错误')
 studio=Path(studio).resolve();contents=studio/'Contents'
 if json.loads((contents/'Resources/product-info.json').read_text()).get('version')!=lock['studioVersion']:raise ValueError('Studio版本不匹配')
 if not lock.get('studioFiles'):raise ValueError('缺少工具锁')
 for rel,expected in lock['studioFiles'].items():
  path=contents/rel
  if not hash_valid(expected) or not path.is_file() or sha(path)!=expected:raise ValueError('Studio工具身份不符：'+rel)
 for path,expected in [(wrapper,lock['cli']['wrapperSHA256']),(common,lock['cli']['commonSHA256'])]:
  if not hash_valid(expected) or not Path(path).is_file() or sha(path)!=expected:raise ValueError('CLI入口身份不符')
 return {'passed':True,'profile':lock.get('profile'),'studioVersion':lock['studioVersion'],'architecture':machine,'studioFiles':lock['studioFiles'],'cli':lock['cli'],'beforeClean':True}
def isolated_hvigor_home(out):
 home=Path(out).resolve()/'hvigor-home'
 if home.is_symlink() or (home.exists() and not home.is_dir()):raise ValueError('隔离Hvigor目录不是受控普通目录')
 home.mkdir(parents=True,exist_ok=True,mode=0o700);return home
def child_environment(env,node,studio,out):
 return {**env,'HVIGOR_USER_HOME':str(isolated_hvigor_home(out)),'PATH':str(node.parent)+os.pathsep+env.get('PATH',''),'DEVECO_CLI_STUDIO_PATH':str(studio),'DEVECO_CLI_DEBUG':'1','DEVECO_CLI_SKIP_VERSION_CHECK':'1'}
def version_line(text):
 lines=re.findall(r'^(v?\d+\.\d+\.\d+)\s*$',text,re.M)
 if len(lines)!=1:raise ValueError('没有唯一合法版本行')
 return lines[0]
def validate_resolution(data,node,common):
 if Path(data['execPath']).resolve()!=Path(node).resolve() or Path(data['common']).resolve()!=Path(common).resolve():raise ValueError('实际CLI common/Node解析与锁不符')
def resolve_cli(node,wrapper,common,root,env,work,rows):
 code="import {createRequire} from 'node:module'; import {realpathSync} from 'node:fs'; console.log(JSON.stringify({execPath:realpathSync(process.execPath),common:realpathSync(createRequire(process.argv[1]).resolve('@deveco/deveco-cli-common/dist/cli.js'))}))"
 text=TARGET.command('cli-resolution',[node,'--input-type=module','-e',code,wrapper],root,env,work,rows,30)
 data=json.loads(text);validate_resolution(data,node,common);return data
def api_metadata(j):
 expected={'compileSdkVersion':'26.0.0.105','minAPIVersion':50003015,'targetAPIVersion':60002022}
 if any(j.get(k)!=v for k,v in expected.items()):raise ValueError('HAR编译/产品API元数据不匹配')
 return {k:j[k] for k in expected}
def redact(text):
 text=re.sub(r'https?://[^\s"\'<>]+',lambda m:m.group(0).split('?',1)[0]+('?<REDACTED>' if '?' in m.group(0) else ''),text)
 return re.sub(r'/(?:private/tmp|Users|Applications|Volumes|home/runner|tmp|opt)/[^\s"\'<>]*','<HOST_PATH>',text)
def result_passed(result,steps_ok):return steps_ok and result.get('passed') is True

def cpp_abi(root,bridge,native,work,rows,env):
 nm=native/'llvm/bin/llvm-nm';readelf=native/'llvm/bin/llvm-readelf'
 def command(name,args):return TARGET.command(name,args,root,env,work,rows,60)
 needed=command('bridge-dynamic',[readelf,'-d',bridge])
 undefined=command('bridge-undefined',[nm,'-D','--undefined-only','--format=posix',bridge])
 imports={line.split()[0] for line in undefined.splitlines() if len(line.split())>=2}
 cpp={s for s in imports if s.startswith('_Z') or s.startswith(('__cxa_guard','__cxa_throw','__cxa_begin','__cxa_end','__gxx'))}
 providers=set()
 for p in sorted((root/'release/inputs/004-normal-core/arm64-v8a').glob('*.so*')):
  text=command('exports-'+p.name,[nm,'-D','--defined-only','--format=posix',p])
  providers.update(line.split()[0] for line in text.splitlines() if len(line.split())>=2)
 missing=sorted(cpp-providers)
 evidence={'passed':not missing,'needed':re.findall(r'Shared library: \[([^\]]+)\]',needed),'cppImports':sorted(cpp),'missingCppProviders':missing,'allUndefined':sorted(imports),'scope':'静态C++提供方核验；平台导入和设备行为仍待consumer/设备验收'}
 if missing:raise ValueError('新bridge需要固定八库未提供的C++符号：'+','.join(missing))
 return evidence

def link_identity(ninja,root):
 text=Path(ninja).read_text()
 flags=re.findall(r'^  LINK_FLAGS = (.*)$',text,re.M);libraries=re.findall(r'^  LINK_LIBRARIES = (.*)$',text,re.M)
 if len(flags)!=1 or len(libraries)!=1 or '-nostdlib++' not in shlex.split(flags[0]):raise ValueError('缺少唯一真实link规则或SDK默认runtime未关闭')
 tokens=shlex.split(libraries[0].replace('$ ',r'\ '))
 if any(t in {'-lc++','-lc++_shared','-lstdc++'} for t in tokens):raise ValueError('真实link仍有自动runtime')
 runtimes=[Path(t).resolve() for t in tokens if t.endswith('/libc++_shared.so')]
 expected=(Path(root)/'release/inputs/004-normal-core/arm64-v8a/libc++_shared.so').resolve()
 if runtimes!=[expected]:raise ValueError('真实link未唯一绑定固定runtime')
 return {'passed':True,'buildNinjaSHA256':sha(ninja),'runtimeSHA256':'9b67147034bfc1d2b7b51b97b638713f90bd8ca9cf4acbcdac6cbc6d155f6042','automaticRuntimeDisabled':True,'linkFlags':flags[0],'linkLibraries':libraries[0]}

def clean_evaluation_native(root):
 # 官方Hvigor只执行ninja clean并删除CMakeCache，保留编译数据库。
 # 这里只清理新评估target自己的未跟踪生成目录，旧default目录不受影响。
 root=Path(root).resolve();relative=Path('packages/vidall-player/.cxx/default/deveco26');target=root/relative
 current=root
 for component in relative.parts:
  current=current/component
  if current.is_symlink():raise ValueError('评估生成路径含符号链接')
 if target.resolve()!=target:raise ValueError('评估生成路径逃逸')
 tracked=subprocess.check_output(['git','-C',str(root),'ls-files','-z','--',str(relative)])
 if tracked:raise ValueError('拒绝删除tracked生成目录')
 files=[]
 if target.exists():
  if not target.is_dir():raise ValueError('评估生成路径不是目录')
  for path in target.rglob('*'):
   if path.is_symlink():raise ValueError('评估生成目录内含符号链接')
   if path.is_file():files.append(str(path.relative_to(target)))
  shutil.rmtree(target)
 return {'path':str(relative),'removedFiles':len(files),'files':sorted(files),'scope':'仅当前隔离checkout的deveco26生成目录'}

def execute(root,out,studio,wrapper,common,env,timeout=1200):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);rows=[];result={'passed':False,'profile':'deveco26-evaluation','commands':rows,'formalArtifactAllowed':False}
 try:
  before=CONTEXT.snapshot(root);result['sourceBefore']=before
  lock=json.loads((HERE/'toolchain-lock.json').read_text());studio=studio.resolve();native=studio/'Contents/sdk/default/openharmony/native';node=studio/'Contents/tools/node/bin/node'
  identity=preflight(studio,wrapper,common,lock,platform.machine());TARGET.sdk_identity(native,lock['native'])
  result['toolchain']=identity;result['lockSHA256']=sha(HERE/'toolchain-lock.json')
  child={**child_environment(env,node,studio,out),'LLVM_NM':str(native/'llvm/bin/llvm-nm')}
  result['environmentIsolation']={'hvigorHomeIsolated':child['HVIGOR_USER_HOME']==str(out.resolve()/'hvigor-home'),'userHomePreserved':child.get('HOME')==env.get('HOME')}
  if Path(shutil.which('node',path=child['PATH']) or '').resolve()!=node.resolve():raise ValueError('子进程PATH选择非锁定Node')
  def cli(name,args):return TARGET.command(name,[node,wrapper,*args],root,child,work,rows,timeout)
  result['cliResolution']=resolve_cli(node,wrapper,common,root,child,work,rows)
  node_version=TARGET.command('node-version',[node,'--version'],root,child,work,rows,30).strip()
  if node_version!=lock['nodeVersion'] or version_line(cli('cli-version',['--version']))!=lock['cli']['version']:raise ValueError('实际Node/CLI版本不符')
  base=root/'release/inputs/004-normal-core';manifest=json.loads((base/'manifest.json').read_text());inputs=TARGET.input_bytes(base,manifest['libraries']);result['inputsBefore']=inputs
  if set(inputs)!=TARGET.NAMES:raise ValueError('固定八库集合不符')
  clean=cli('clean',['build','clean']);selected,_=TARGET.selected_studio(clean)
  if Path(selected).resolve()!=studio:raise ValueError('clean选择不同Studio')
  result['nativeClean']=clean_evaluation_native(root)
  output=root/'packages/vidall-player/build/default/outputs/deveco26';cc=root/'packages/vidall-player/.cxx/default/deveco26/debug/arm64-v8a/compile_commands.json';bridge=root/'packages/vidall-player/build/default/intermediates/stripped_native_libs/deveco26/arm64-v8a/libvidall_player_native.so'
  if list(output.glob('*.har')) or cc.exists() or bridge.exists():raise ValueError('clean残留旧输出')
  TARGET.command('input-audit',[sys.executable,'-B',root/'scripts/audit/normal-core-verify.py'],root,child,work,rows,120)
  built=cli('har-build',['build','--modules','vidall_player@deveco26']);selected,_=TARGET.selected_studio(built)
  if Path(selected).resolve()!=studio:raise ValueError('build选择不同Studio')
  hars=list(output.glob('*.har'))
  if len(hars)!=1:raise ValueError('缺少唯一HAR')
  result['artifact']=TARGET.verify_har(hars[0],manifest['libraries'],bridge)
  with tarfile.open(hars[0]) as t:
   result['api']=api_metadata(json.load(t.extractfile('package/src/main/module.json'))['app'])
  result['compiledSources']=TARGET.compiled_sources(root,cc,native)
  required={'packages/vidall-player/src/main/cpp/napi_init.cpp','native/runtime/process_runtime.cpp'}
  if not required.issubset({x['source'] for x in result['compiledSources']}):raise ValueError('缺少真实产品编译单元')
  result['linkIdentity']=link_identity(cc.parent/'build.ninja',root)
  result['compileCommandsSHA256']=sha(cc);result['abi']=cpp_abi(root,bridge,native,work,rows,child)
  if TARGET.input_bytes(base,manifest['libraries'])!=inputs:raise ValueError('构建修改固定八库')
  preflight(studio,wrapper,common,lock,platform.machine());result['sourceAfter']=CONTEXT.assert_snapshot(root,before);result['passed']=True
 except Exception as e:result.update(errorType=type(e).__name__,error=redact(str(e)))
 (work/'evaluation-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def publish(root,out,steps_ok):
 work=out/'work';public=out/'public';public.mkdir(parents=True,exist_ok=True)
 def read(name):
  try:return json.loads((work/name).read_text())
  except (OSError,ValueError):return {}
 context=read('context.json');result=read('evaluation-result.json');valid=False
 try:
  expected={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']};CONTEXT.assert_snapshot(root,expected)
  valid=context.get('passed') is True and result.get('sourceBefore')==expected and result.get('sourceAfter')==expected and read('bootstrap-result.json').get('passed') is True
 except (KeyError,ValueError,OSError):pass
 status={'passed':result_passed(result,steps_ok and valid),'sourceBound':valid,'formalArtifactAllowed':False}
 (work/'evaluation-status.json').write_text(json.dumps(status,indent=2)+'\n')
 for p in sorted(work.iterdir()):
  if p.suffix not in {'.json','.log'}:continue
  if p.is_symlink() or p.stat().st_size>10*1024*1024:raise ValueError('拒绝异常证据文件')
  (public/p.name).write_text(redact(p.read_text()))
 index=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.iterdir()) if p.name!='index.json']
 (public/'index.json').write_text(json.dumps({'files':index,'formalArtifactAllowed':False},indent=2)+'\n')
 if load('check-public').verify(public):raise ValueError('公开证据边界失败')
 return status

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','finish','assess']);p.add_argument('--out',type=Path,required=True);p.add_argument('--studio',type=Path);p.add_argument('--wrapper',type=Path);p.add_argument('--common',type=Path);a=p.parse_args()
 if a.mode=='assess':return 0 if json.loads((a.out/'public/evaluation-status.json').read_text()).get('passed') else 1
 if a.mode=='finish':
  steps=json.loads(os.environ.get('CI_STEPS','{}'));ok=all(steps.get(k,{}).get('outcome')=='success' for k in ['context','contracts','bootstrap','runtime','target','cleanup']);r=publish(ROOT,a.out,ok);print(json.dumps(r));return 0
 else:
  context=json.loads((a.out/'work/context.json').read_text())
  if not context.get('passed') or not context.get('trustedTarget'):raise ValueError('缺少可信事件')
  CONTEXT.assert_snapshot(ROOT,{k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']})
  r=execute(ROOT,a.out,a.studio,a.wrapper,a.common,dict(os.environ))
 print(json.dumps({'passed':r['passed'],'formalArtifactAllowed':False}));return 0 if r['passed'] else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print('评估失败：'+type(e).__name__,file=sys.stderr);raise SystemExit(1)
