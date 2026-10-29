#!/usr/bin/env python3
"""在隔离无签名工程编译完整旧Hypium，消费本次HAR；不声明设备运行通过。"""
import argparse,importlib.util,json,os,re,shutil,zipfile,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
s=importlib.util.spec_from_file_location('consumer010',HERE.parent/'deveco26-gates/consumer.py');C=importlib.util.module_from_spec(s);s.loader.exec_module(C);E=C.E
SUITES={'playerSessionTest','streamingSessionTest','streamingInternalsTest','mediaKindDetectionTest','demoLifecycleTest','trackPresentationTest','videoLetterboxTest','webDavServiceTest','sessionInfrastructureTest'}
def suite_sources(base):
 files=sorted(p for p in base.rglob('*') if p.is_file())
 if not files or any(p.is_symlink() for p in base.rglob('*')):raise ValueError('测试源码集合缺失或符号链接')
 return {str(p.relative_to(base)):E.sha(p) for p in files}
def prepare_project(root,project,har):
 C.prepare_project(root,project,har)
 # 测试的相对导入仍指向原demo代码；只编译，不安装该旧运行契约。
 shutil.rmtree(project/'entry/src/main')
 for rel in ['entry/src/main','entry/src/ohosTest']:
  src=root/rel
  if any(p.is_symlink() for p in src.rglob('*')):raise ValueError('Hypium源码符号链接拒绝')
  shutil.copytree(src,project/rel,ignore=shutil.ignore_patterns('cpp'))
 text=(project/'entry/src/ohosTest/ets/test/List.test.ets').read_text();suites=re.findall(r'^import\s+(\w+)\s+from ',text,re.M)
 if set(suites)!=SUITES or len(suites)!=len(SUITES):raise ValueError('Hypium九套测试集合漂移')
 if any(re.search(r"from\s*['\"]libentry",p.read_text()) for p in (project/'entry/src').rglob('*.ets')):raise ValueError('测试依赖未纳入HAR的旧libentry')
 def write(rel,data):(project/rel).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 write('entry/build-profile.json5',{'apiType':'stageMode','buildOption':{},'targets':[{'name':'default'},{'name':'ohosTest'}]})
 package=json.loads((root/'oh-package.json5').read_text());write('oh-package.json5',{'modelVersion':package['modelVersion'],'dependencies':{},'devDependencies':package['devDependencies']})
 app=json.loads((project/'AppScope/app.json5').read_text());app['app']['bundleName']='com.yaoshining.cloudhypium';write('AppScope/app.json5',app)
 return {'suites':sorted(suites),'sources':suite_sources(project/'entry/src/ohosTest'),'mode':'compile-only-unsigned'}
def compiled_output(path):
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if len(names)!=len(set(names)):raise ValueError('Hypium包含重复成员')
  data=json.loads(z.read('module.json'))
  if data.get('module',{}).get('name')!='entry_test' or 'ets/modules.abc' not in names or not z.read('ets/modules.abc'):raise ValueError('无真实entry_test编译字节码')
  raw=z.read('ets/modules.abc');abc=hashlib.sha256(raw).hexdigest()
 return {'compiled':True,'hapSHA256':E.sha(path),'bytecodeSHA256':abc,'bytecodeBytes':len(raw),'moduleName':data['module']['name']}
def proof(r,source,target):
 try:
  artifact=r['artifact'];expected=target['artifact'];libraries=expected['libraries']
  return r.get('passed') is True and r.get('sourceBefore')==source==r.get('sourceAfter') and r.get('inputHAR')==expected['harSHA256'] and r.get('compiled') is True and r.get('signed') is False and r.get('executed') is False and r.get('cleanup',{}).get('passed') is True and r.get('suiteNames')==sorted(SUITES) and r.get('dependency',{}).get('passed') is True and r['dependency'].get('installedLibraries')==libraries and artifact.get('passed') is True and artifact.get('libraries')==libraries and set(libraries)==E.TARGET.NAMES|{'libvidall_player_native.so'} and artifact.get('api')==target['api'] and E.hash_valid(artifact.get('hapSHA256')) and E.hash_valid(r.get('bytecodeSHA256')) and type(r.get('bytecodeBytes')) is int and r['bytecodeBytes']>0 and r.get('moduleName')=='entry_test' and r.get('stagedSources')==suite_sources(ROOT/'entry/src/ohosTest') and type(r.get('buildExit')) is int and r['buildExit']==0
 except (KeyError,TypeError,ValueError,OSError):return False

def execute(root,out,studio,wrapper,common):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);project=out/'hypium/project';rows=[];result={'passed':False,'compiled':False,'signed':False,'executed':False,'commands':rows,'formalArtifactAllowed':False};child=None
 try:
  source=E.CONTEXT.snapshot(root);target=json.loads((work/'evaluation-result.json').read_text());context=json.loads((work/'context.json').read_text());expected={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']}
  if not target.get('passed') or target.get('sourceBefore')!=source or target.get('sourceAfter')!=source or source!=expected:raise ValueError('Hypium与target事件源码不符')
  result['sourceBefore']=source;hars=list((root/'packages/vidall-player/build/default/outputs/deveco26').glob('*.har'))
  if len(hars)!=1:raise ValueError('缺少唯一当次HAR')
  har=hars[0];result['inputHAR']=target['artifact']['harSHA256'];C.verify_har_digest(har,result['inputHAR']);libraries=target['artifact']['libraries']
  lock=json.loads((HERE.parent/'deveco26/toolchain-lock.json').read_text());result['toolchain']=C.verify_consumer_toolchain(studio,wrapper,common,lock);node=studio/'Contents/tools/node/bin/node';child=E.child_environment(dict(os.environ),node,studio,out/'hypium')
  prepared=prepare_project(root,project,har);result.update(suiteNames=prepared['suites'],stagedSources=prepared['sources'],mode=prepared['mode']);dest=project/'entry/libs/current.har'
  for name,args in [('hypium-clean',['build','clean']),('hypium-build',['build','--modules','entry@ohosTest'])]:
   output=E.TARGET.command(name,[node,wrapper,*args],project,child,work,rows,1200)
   selected,_=E.TARGET.selected_studio(output)
   if Path(selected).resolve()!=studio.resolve():raise ValueError('Hypium混用SDK')
   if name=='hypium-clean' and list((project/'entry/build').rglob('*.hap')):raise ValueError('Hypium clean残留HAP')
  result['buildExit']=rows[-1]['exit'];haps=list((project/'entry/build/default/outputs/ohosTest').glob('*-unsigned.hap'))
  if len(haps)!=1:raise ValueError('缺少唯一unsigned Hypium HAP')
  result['artifact']=C.verify_hap(haps[0],libraries);result.update(compiled_output(haps[0]));result['dependency']=C.installed_identity(project,libraries,dest)
  if suite_sources(project/'entry/src/ohosTest')!=result['stagedSources'] or result['stagedSources']!=suite_sources(root/'entry/src/ohosTest'):raise ValueError('Hypium测试源码漂移')
  C.verify_har_digest(dest,result['inputHAR']);C.verify_har_digest(har,result['inputHAR']);result.update(sourceAfter=E.CONTEXT.assert_snapshot(root,source),passed=True)
 except Exception as error:result.update(errorType=type(error).__name__,error=E.redact(str(error)))
 finally:
  if child is not None and project.is_dir():
   try:result['cleanup']=C.stop_project(project,child,studio,work,rows,'hypium')
   except Exception as error:result.update(passed=False,cleanup={'passed':False,'errorType':type(error).__name__})
 (work/'hypium-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--studio',type=Path,required=True);p.add_argument('--wrapper',type=Path,required=True);p.add_argument('--common',type=Path,required=True);a=p.parse_args();r=execute(ROOT,a.out.resolve(),a.studio.resolve(),a.wrapper.resolve(),a.common.resolve());print(json.dumps({'passed':r['passed'],'compiled':r['compiled'],'executed':False}));raise SystemExit(0 if r['passed'] else 1)
