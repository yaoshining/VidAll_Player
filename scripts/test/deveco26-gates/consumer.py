#!/usr/bin/env python3
"""同一任务内构建实际HAR消费者；二进制仅保留在临时目录，公开文本证据。"""
import argparse,hashlib,io,importlib.util,json,os,platform,re,shutil,subprocess,sys,tarfile,time,zipfile
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
E=module('evaluate007',HERE.parent/'deveco26/evaluate.py');B=module('bootstrap007',HERE.parent/'deveco26/bootstrap.py')
APIS=['initializePlayerRuntime','onPlayerTerminal','getPlayerRuntimeStatus','createPlayer']
def verify_har_digest(har,expected):
 if not E.hash_valid(expected) or har.is_symlink() or not har.is_file() or E.sha(har)!=expected:raise ValueError('HAR不是本次target已核输出')
def verify_hap(path,libraries):
 if set(libraries)!=E.TARGET.NAMES|{'libvidall_player_native.so'}:raise ValueError('预期九库集合不符')
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if len(names)!=len(set(names)) or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts for n in names):raise ValueError('HAP重复或异常路径')
  actual={}
  for n in names:
   if n.startswith('libs/') and not n.endswith('/'):
    if not n.startswith('libs/arm64-v8a/') or '/' in n[len('libs/arm64-v8a/'):]:raise ValueError('HAP含非预期架构/嵌套库')
    actual[n.split('/')[-1]]=hashlib.sha256(z.read(n)).hexdigest()
  if actual!=libraries:raise ValueError('HAP九库与当次HAR不一致')
  api=E.api_metadata(json.loads(z.read('module.json'))['app'])
 return {'passed':True,'hapSHA256':E.sha(path),'libraries':actual,'api':api,'signed':False,'deviceVerified':False}
def resolution_lock(entry,har,lock):
 matches=[v for v in lock.get('packages',{}).values() if v.get('name')=='@vidall/player']
 if len(matches)!=1 or matches[0].get('registryType')!='local':raise ValueError('缺少唯一HAR本地解析')
 target=matches[0].get('resolved','').removeprefix('file:')
 if (entry/target).resolve()!=har.resolve() or not har.is_file() or har.suffix!='.har':raise ValueError('依赖解析为源码/旧HAR/其他缓存')
 return {'passed':True,'resolved':'entry/libs/current.har','registryType':'local','lockSHA256':hashlib.sha256(json.dumps(lock,sort_keys=True).encode()).hexdigest()}
def owned_pids(home,project):
 p=home/'daemon/cache/daemon-sec.json'
 for part in [home,home/'daemon',home/'daemon/cache',p]:
  if part.is_symlink():raise ValueError('consumer registry符号链接拒绝')
 if not p.exists():return set()
 expected=set();data=json.loads(p.read_text())
 if not isinstance(data,dict):raise ValueError('consumer registry格式错误')
 for item in data.values():
  if not isinstance(item,dict):raise ValueError('consumer registry entry错误')
  if Path(item.get('cwdPath','')).resolve()==project.resolve():
   pid=item.get('pid')
   if type(pid) is not int or pid<=0:raise ValueError('consumer PID非法')
   expected.add(pid)
 return expected

def prepare_project(root,project,har):
 if project.exists():raise ValueError('拒绝复用已存在consumer工程')
 fixture=root/'fixtures/normal-core-consumer';project.mkdir(parents=True)
 for rel in ['AppScope','entry/src/main','hvigor']:
  source=fixture/rel
  if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('fixture符号链接拒绝')
  shutil.copytree(source,project/rel)
 for rel in ['hvigorfile.ts','entry/hvigorfile.ts']:shutil.copyfile(fixture/rel,project/rel)
 text=(project/'entry/src/main/ets/pages/Index.ets').read_text();match=re.search(r'import\s*\{([^}]+)\}\s*from\s*[\'"]@vidall/player[\'"]',text)
 if not match or not all(api in match.group(1) for api in APIS):raise ValueError('consumer未使用新公共根API')
 if re.search(r"from ['\"].*(?:src/internal|libvidall_player_native)",text):raise ValueError('consumer越过公共根入口')
 def write(rel,data):(project/rel).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 write('build-profile.json5',{'app':{'signingConfigs':[],'products':[{'name':'default','targetSdkVersion':'6.0.2(22)','compatibleSdkVersion':'5.0.3(15)','runtimeOS':'HarmonyOS','buildOption':{'strictMode':{'caseSensitiveCheck':True,'useNormalizedOHMUrl':True}}}],'buildModeSet':[{'name':'debug'}]},'modules':[{'name':'entry','srcPath':'./entry','targets':[{'name':'default','applyToProducts':['default']}]}]})
 write('oh-package.json5',{'modelVersion':'6.0.2','dependencies':{},'devDependencies':{}})
 write('entry/build-profile.json5',{'apiType':'stageMode','buildOption':{},'targets':[{'name':'default'}]})
 write('entry/oh-package.json5',{'name':'entry','version':'1.0.0','dependencies':{'@vidall/player':'file:./libs/current.har'}})
 dest=project/'entry/libs/current.har';dest.parent.mkdir();shutil.copyfile(har,dest)
 return dest

def installed_identity(project,libraries,har):
 lock=json.loads((project/'entry/oh-package-lock.json5').read_text());result=resolution_lock(project/'entry',project/'entry/libs/current.har',lock)
 candidates=[project/'entry/oh_modules/@vidall/player',project/'oh_modules/@vidall/player'];found=[p.resolve() for p in candidates if p.exists()]
 if not found:raise ValueError('缺少实际展开的HAR依赖')
 actual=found[0]
 if any(p!=actual for p in found):raise ValueError('存在不同来源的player解析')
 if not actual.is_relative_to(project.resolve()):raise ValueError('解析逃逸到工程外源码或旧缓存')
 libdir=actual/'libs/arm64-v8a';hashes={p.name:E.sha(p) for p in libdir.iterdir() if p.is_file()}
 if hashes!=libraries:raise ValueError('展开依赖九库并非当次HAR')
 with tarfile.open(har) as t:expected=hashlib.sha256(t.extractfile('package/Index.d.ets').read()).hexdigest()
 if E.sha(actual/'Index.d.ets')!=expected:raise ValueError('展开公共声明不是当次HAR')
 result.update(installedRootInsideProject=True,installedLibraries=hashes,publicDeclarationSHA256=expected)
 return result

def stop_project(project,child,studio,work,rows,prefix="consumer"):
 end=time.monotonic()+90;home=Path(child['HVIGOR_USER_HOME']);expected=owned_pids(home,project)
 node=studio/'Contents/tools/node/bin/node';B.verify_cleanup_tools(studio)
 output=E.TARGET.command(prefix+'-stop-daemon',[node,studio/'Contents/tools/hvigor/bin/hvigorw.js','--stop-daemon'],project,child,work,rows,60)
 pids=B.stopped_pids(output,expected);B.wait_owned_pids(pids,end)
 return {'passed':True,'stoppedOwnedPids':pids,'registryProjectMatched':True,'hvigorHomeIsolated':True,'userHOMEChanged':False}

def verify_consumer_toolchain(studio,wrapper,common,lock):
 return E.preflight(studio,wrapper,common,lock,platform.machine())

def execute(root,out,studio,wrapper,common):
 root=root.resolve();out=out.resolve();work=out/'work';work.mkdir(parents=True,exist_ok=True);project=out/'consumer/project';rows=[];result={'passed':False,'commands':rows,'formalArtifactAllowed':False};child=None
 try:
  source=E.CONTEXT.snapshot(root);target=json.loads((work/'evaluation-result.json').read_text());context=json.loads((work/'context.json').read_text());expected={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']}
  if not target.get('passed') or target.get('sourceBefore')!=source or target.get('sourceAfter')!=source or source!=expected:raise ValueError('target/consumer不属于同一事件源码')
  result['sourceBefore']=source
  files=list((root/'packages/vidall-player/build/default/outputs/deveco26').glob('*.har'))
  if len(files)!=1:raise ValueError('不是唯一deveco26产出HAR')
  har=files[0];verify_har_digest(har,target['artifact']['harSHA256']);result['inputHAR']=target['artifact']['harSHA256'];result['libraries']=target['artifact']['libraries']
  lock=json.loads((HERE.parent/'deveco26/toolchain-lock.json').read_text());result['toolchain']=verify_consumer_toolchain(studio,wrapper,common,lock);node=studio/'Contents/tools/node/bin/node';child=E.child_environment(dict(os.environ),node,studio,out/'consumer')
  dest=prepare_project(root,project,har);verify_har_digest(dest,result['inputHAR'])
  result['fixtureSourceSHA256']=E.sha(project/'entry/src/main/ets/pages/Index.ets');result['fixture']='fixtures/normal-core-consumer/entry/src/main';result['publicRootAPIs']=APIS
  for name,args in [('consumer-clean',['build','clean']),('consumer-build',['build','--modules','entry@default'])]:
   output=E.TARGET.command(name,[node,wrapper,*args],project,child,work,rows,1200)
   selected,_=E.TARGET.selected_studio(output)
   if Path(selected).resolve()!=studio.resolve():raise ValueError('consumer混用SDK')
   if name=='consumer-clean' and list((project/'entry/build').rglob('*.hap')):raise ValueError('consumer clean残留HAP')
  result['dependency']=installed_identity(project,result['libraries'],dest)
  haps=list((project/'entry/build/default/outputs/default').glob('*-unsigned.hap'))
  if len(haps)!=1:raise ValueError('缺少唯一unsigned HAP')
  result['artifact']=verify_hap(haps[0],result['libraries']);verify_har_digest(dest,result['inputHAR']);verify_har_digest(har,result['inputHAR'])
  if E.sha(project/'entry/src/main/ets/pages/Index.ets')!=result['fixtureSourceSHA256']:raise ValueError('consumer源码漂移')
  result['sourceAfter']=E.CONTEXT.assert_snapshot(root,source);result['passed']=True
 except Exception as error:result.update(errorType=type(error).__name__,error=E.redact(str(error)))
 finally:
  if child is not None and project.is_dir():
   try:result['cleanup']=stop_project(project,child,studio,work,rows)
   except Exception as error:result.update(passed=False,cleanup={'passed':False,'errorType':type(error).__name__})
  else:result['cleanup']={'passed':False,'notStarted':True}
 (work/'consumer-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def missing_api_diagnostic(text,exit_code):
 return type(exit_code) is int and exit_code!=0 and bool(re.search(r"has no exported member ['\"]initializePlayerRuntime['\"]",text))

def negative_api(root,out,studio,wrapper,common):
 work=out/'work';project=out/'consumer-negative/project';rows=[];result={'passed':False,'commands':rows,'formalArtifactAllowed':False};child=None
 try:
  source=E.CONTEXT.snapshot(root);target=json.loads((work/'evaluation-result.json').read_text())
  if not target.get('passed') or target.get('sourceBefore')!=source or target.get('sourceAfter')!=source:raise ValueError('负例target源码不匹配')
  hars=list((root/'packages/vidall-player/build/default/outputs/deveco26').glob('*.har'))
  if len(hars)!=1:raise ValueError('负例缺少唯一当前HAR')
  har=hars[0];verify_har_digest(har,target['artifact']['harSHA256']);dest=prepare_project(root,project,har);before=E.sha(dest)
  lock=json.loads((HERE.parent/'deveco26/toolchain-lock.json').read_text());verify_consumer_toolchain(studio,wrapper,common,lock);node=studio/'Contents/tools/node/bin/node';child=E.child_environment(dict(os.environ),node,studio,out/'consumer-negative')
  mutated=dest.with_suffix('.mutated.har');changes=[]
  with tarfile.open(dest) as original,tarfile.open(mutated,'w:gz') as output:
   for item in original.getmembers():
    if item.isreg():
     data=original.extractfile(item).read()
     if item.name=='package/Index.d.ets':
      if data.count(b'initializePlayerRuntime,')!=1:raise ValueError('未找到唯一待删除公共API')
      data=data.replace(b'initializePlayerRuntime,',b'',1);item.size=len(data);changes.append(item.name)
     output.addfile(item,io.BytesIO(data))
    else:output.addfile(item)
  if changes!=['package/Index.d.ets']:raise ValueError('负例修改集合不符')
  mutated.replace(dest);result['mutation']={'originalHAR':before,'mutantHAR':E.sha(dest),'changedMembers':changes,'removedPublicAPI':'initializePlayerRuntime'}
  E.TARGET.command('consumer-negative-clean',[node,wrapper,'build','clean'],project,child,work,rows,1200)
  try:E.TARGET.command('consumer-negative-build',[node,wrapper,'build','--modules','entry@default'],project,child,work,rows,1200)
  except RuntimeError:pass
  text=(work/'consumer-negative-build.log').read_text();selected,_=E.TARGET.selected_studio(text)
  if Path(selected).resolve()!=studio.resolve() or not missing_api_diagnostic(text,rows[-1]['exit']):raise ValueError('未观察到指定公共API缺失的ArkTS编译失败')
  if list((project/'entry/build').rglob('*.hap')):raise ValueError('缺API负例不应生成HAP')
  verify_har_digest(har,before);result.update(passed=True,specificArkTSDiagnostic=True,sourceBefore=source,sourceAfter=E.CONTEXT.assert_snapshot(root,source))
 except Exception as error:result.update(errorType=type(error).__name__,error=E.redact(str(error)))
 finally:
  if child is not None and project.is_dir():
   try:result['cleanup']=stop_project(project,child,studio,work,rows,'consumer-negative')
   except Exception as error:result.update(passed=False,cleanup={'passed':False,'errorType':type(error).__name__})
 (work/'consumer-negative-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--negative-api',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--studio',type=Path,required=True);p.add_argument('--wrapper',type=Path,required=True);p.add_argument('--common',type=Path,required=True);a=p.parse_args();r=(negative_api if a.negative_api else execute)(ROOT,a.out,a.studio.resolve(),a.wrapper.resolve(),a.common.resolve());print(json.dumps({'passed':r['passed'],'formalArtifactAllowed':False}));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
