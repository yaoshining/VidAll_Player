#!/usr/bin/env python3
"""真正编译当前 Player HAR；只消费固定八库，不重建 producer。"""
import argparse,hashlib,importlib.util,json,os,re,shlex,signal,subprocess,sys,tarfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
NAMES={'libmpv.so','libavcodec.so.62','libavformat.so.62','libavfilter.so.11','libavutil.so.60','libswresample.so.6','libswscale.so.9','libc++_shared.so'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name):
 spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def command(name,args,root,env,work,rows,timeout):
 started=time.monotonic()
 try:
  process=subprocess.Popen([str(a) for a in args],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
  try:text=process.communicate(timeout=timeout)[0];code=process.returncode
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGKILL);text=process.communicate()[0];code='timeout'
 except OSError as error:code='launch-error';text=str(error)
 (work/(name+'.log')).write_text(text);rows.append({'name':name,'exit':code,'seconds':round(time.monotonic()-started,3),'passed':code==0})
 if code!=0:raise RuntimeError(name+' 失败：'+str(code))
 return text

def selected_studio(text):
 found=re.findall(r'\[ToolProvider\] Using auto → (.+) \(([^\n]+)\)',text)
 explicit=re.findall(r'\[ToolProvider\] Using (DEVECO_CLI_STUDIO_PATH|DEVECO_HOME|DEVECO_PATH) → (.+)',text)
 pairs=set(found+[(p.strip(),'explicit') for _,p in explicit])
 if len(pairs)!=1:raise ValueError('devecocli 未给出唯一 Studio 选择；不能猜测 SDK 路径')
 return next(iter(pairs))

def sdk_identity(native,lock):
 metadata=json.loads((native/'oh-uni-package.json').read_text())
 if metadata.get('apiVersion')!=lock['apiVersion'] or metadata.get('version')!=lock['version']:raise ValueError('SDK API/version 与已审查目标不符')
 if not (native/'sysroot').is_dir():raise ValueError('SDK sysroot 缺失')
 rows={}
 for name,expected in lock['files'].items():
  p=native/name
  if not p.is_file() or sha(p)!=expected:raise ValueError('SDK 工具/metadata 身份不符：'+name)
  if name.startswith('llvm/bin/') and not os.access(p,os.X_OK):raise ValueError('SDK 工具不可执行')
  rows[name]=expected
 return {'passed':True,'apiVersion':metadata['apiVersion'],'version':metadata['version'],'files':rows}

def discover_sdk(root,env,work,rows,lock):
 probeenv={**env,'DEVECO_CLI_DEBUG':'1','DEVECO_CLI_SKIP_VERSION_CHECK':'1'}
 text=command('toolchain-probe',['devecocli','docs','catalog'],root,probeenv,work,rows,60)
 studio,version=selected_studio(text);studio=Path(studio).resolve();native=studio/'Contents/sdk/default/openharmony/native'
 identity=sdk_identity(native,lock);identity['selectionVersion']=version
 # Build and probe must use the same official CLI selection, never another auto SDK.
 child={**env,'DEVECO_CLI_STUDIO_PATH':str(studio),'LLVM_NM':str(native/'llvm/bin/llvm-nm')}
 (work/'toolchain.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2)+'\n')
 command('devecocli-version',['devecocli','--version'],root,child,work,rows,30)
 return child,native

def input_bytes(base,libraries):
 result={}
 for row in libraries:
  p=base/row['path']
  if not p.is_file() or sha(p)!=row['sha256']:raise ValueError('固定输入缺失或漂移：'+row['path'])
  result[Path(row['path']).name]=row['sha256']
 return result

def verify_har(har,libraries,bridge):
 expected={Path(r['path']).name:r['sha256'] for r in libraries}
 if set(expected)!=NAMES or len(libraries)!=8:raise ValueError('固定八库集合错误')
 normal=load('normalize-har');actual={}
 with tarfile.open(har,'r:*') as archive:
  for item in normal.members(archive):
   prefix='package/libs/arm64-v8a/'
   if item.isreg() and item.name.startswith(prefix):
    name=item.name[len(prefix):];data=archive.extractfile(item).read();actual[name]=hashlib.sha256(data).hexdigest()
    if name=='libvidall_player_native.so':
     if len(data)<20 or data[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(data[18:20],'little')!=183:raise ValueError('bridge 不是ARM64 ELF')
 if set(actual)!=NAMES|{'libvidall_player_native.so'}:raise ValueError('HAR ARM64九库集合不完整或混装')
 if any(actual[n]!=h for n,h in expected.items()):raise ValueError('HAR核心库与锁定输入不符')
 if not bridge.is_file() or actual['libvidall_player_native.so']!=sha(bridge):raise ValueError('HAR bridge不是本次目标输出')
 return {'passed':True,'harSHA256':sha(har),'libraries':actual,'formalArtifactAllowed':False}

def compiled_sources(root,cc,native):
 units=json.loads(cc.read_text());sources=[]
 if not units:raise ValueError('目标编译单元为空')
 for unit in units:
  args=unit.get('arguments') or shlex.split(unit['command']);compiler=Path(args[0]).resolve()
  if compiler!= (native/'llvm/bin/clang').resolve():raise ValueError('实际编译器不属于核验SDK')
  sysroots=[x.split('=',1)[1] for x in args if x.startswith('--sysroot=')]
  if len(sysroots)!=1 or Path(sysroots[0]).resolve()!=(native/'sysroot').resolve():raise ValueError('实际sysroot与核验SDK不符')
  source=Path(unit['file']).resolve();relative=source.relative_to(root.resolve())
  sources.append({'source':str(relative),'sha256':sha(source),'compilerSHA256':sha(compiler)})
 return sources

def execute(root,out,env,timeout=1200):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);rows=[];result={'passed':False,'commands':rows,'formalArtifactAllowed':False}
 try:
  identity=load('ci-context');before_source=identity.snapshot(root);result['sourceBefore']=before_source
  lock=json.loads((HERE/'ci-toolchain-lock.json').read_text());child,native=discover_sdk(root,env,work,rows,lock)
  base=root/'release/inputs/004-normal-core';manifest=json.loads((base/'manifest.json').read_text());before=input_bytes(base,manifest['libraries'])
  if set(before)!=NAMES:raise ValueError('固定八库集合不符')
  command('input-audit',[sys.executable,'-B',root/'scripts/audit/normal-core-verify.py'],root,child,work,rows,120)
  command('clean',['devecocli','build','clean'],root,child,work,rows,timeout)
  output=root/'packages/vidall-player/build/default/outputs/default'
  cc=root/'packages/vidall-player/.cxx/default/default/debug/arm64-v8a/compile_commands.json'
  bridge=root/'packages/vidall-player/build/default/intermediates/stripped_native_libs/default/arm64-v8a/libvidall_player_native.so'
  if list(output.glob('*.har')) or cc.exists() or bridge.exists():raise ValueError('clean后仍有旧HAR/bridge/compile_commands，拒绝复用')
  command('har-build',['devecocli','build','--modules','vidall_player@default'],root,child,work,rows,timeout)
  hars=list(output.glob('*.har'))
  if len(hars)!=1:raise ValueError('构建未产生唯一HAR')
  bridge=root/'packages/vidall-player/build/default/intermediates/stripped_native_libs/default/arm64-v8a/libvidall_player_native.so'
  result['artifact']=verify_har(hars[0],manifest['libraries'],bridge)
  if input_bytes(base,manifest['libraries'])!=before:raise ValueError('构建修改固定输入')
  cc=root/'packages/vidall-player/.cxx/default/default/debug/arm64-v8a/compile_commands.json'
  sources=compiled_sources(root,cc,native)
  required={'packages/vidall-player/src/main/cpp/napi_init.cpp','native/runtime/process_runtime.cpp'}
  if not required.issubset({r['source'] for r in sources}):raise ValueError('目标编译单元缺失当前产品源码')
  result['sourceAfter']=identity.assert_snapshot(root,before_source)
  result.update(passed=True,inputs=before,compiledSources=sources,compileCommandsSHA256=sha(cc))
 except Exception as error:result['error']=str(error)
 (work/'target-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 context=json.loads((args.out/'work/context.json').read_text())
 if not context.get('passed') or not context.get('trustedTarget'):raise ValueError('目标门禁缺少可信事件身份')
 load('ci-context').assert_snapshot(ROOT,{k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']})
 result=execute(ROOT,args.out,dict(os.environ));print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:print('目标门禁失败：'+str(error),file=sys.stderr);raise SystemExit(1)
