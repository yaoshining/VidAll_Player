#!/usr/bin/env python3
"""独立短测unsigned设备包；严格消费同源码target HAR，不签名、不上传、不访问设备。"""
import argparse,hashlib,importlib.util,json,os,re,shutil,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
D=module('device_contract_package',HERE.parent/'device-execution/controller.py')
C=module('consumer_device_package',HERE.parent/'deveco26-gates/consumer.py');E=C.E
BUNDLE='com.yaoshining.vidalldeviceprobe'
FIXTURE_FILES = {
 'AppScope/app.json5',
 'AppScope/resources/base/element/string.json',
 'AppScope/resources/base/media/probe.svg',
 'entry/hvigorfile.ts',
 'entry/src/main/ets/entryability/EntryAbility.ets',
 'entry/src/main/ets/pages/Index.ets',
 'entry/src/main/ets/smoke/LaunchSession.ets',
 'entry/src/main/ets/smoke/PlatformPort.ets',
 'entry/src/main/ets/smoke/SessionJournal.ets',
 'entry/src/main/ets/smoke/SmokeSession.ets',
 'entry/src/main/module.json5',
 'entry/src/main/resources/base/element/color.json',
 'entry/src/main/resources/base/element/string.json',
 'entry/src/main/resources/base/media/probe.svg',
 'entry/src/main/resources/base/profile/main_pages.json',
 'entry/src/main/resources/rawfile/test_video.mp4',
 'hvigor/hvigor-config.json5',
 'hvigorfile.ts',
 'media-lock.json',
}

def validate_fixture(root):
 base=root/'fixtures/device-smoke'
 if base.is_symlink() or not base.is_dir() or any(p.is_symlink() for p in base.rglob('*')):raise ValueError('fixture缺失或符号链接')
 if {str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()}!=FIXTURE_FILES:raise ValueError('fixture文件集不在已审白名单')
 config=json.loads((base/'entry/src/main/module.json5').read_text())['module'];app=json.loads((base/'AppScope/app.json5').read_text())['app']
 if app['bundleName']!=BUNDLE or config.get('name')!='entry' or config.get('requestPermissions') or config.get('extensionAbilities'):raise ValueError('设备包bundle/网络/扩展不符合约束')
 if len(config.get('abilities',[]))!=1 or config['abilities'][0]['name']!='EntryAbility':raise ValueError('入口能力不符')
 sources=sorted((base/'entry/src/main/ets').rglob('*.ets'));text='\n'.join(p.read_text() for p in sources)
 if any(token in text for token in ['PrivateSmb','credentials','smb://','http://','https://','libvidall_player_native','src/internal','getPreferences','BackupExtensionAbility']):raise ValueError('设备入口包含私人/网络/内部接口能力')
 platform=(base/'entry/src/main/ets/smoke/PlatformPort.ets').read_text();m=re.search(r'import\s*\{([^}]+)\}\s*from\s*[\'"]@vidall/player[\'"]',platform)
 if not m or not all(api in m.group(1) for api in C.APIS):raise ValueError('设备包缺公共根API')
 media=json.loads((base/'media-lock.json').read_text());E.verify_file(base/'entry/src/main'/media['path'],media['bytes'],media['sha256'])
 if media['origin']!='generated-synthetic' or media['generatorSHA256']!=E.sha(root/'scripts/test/device-package/generate_media.py') or media['path']!='resources/rawfile/test_video.mp4':raise ValueError('媒体生成器/来源不符')
 return {'passed':True,'media':media,'fixtureSources':{str(p.relative_to(base)):E.sha(p) for p in sorted(base.rglob('*')) if p.is_file()},'entrySourceSHA256':E.sha(base/'entry/src/main/ets/pages/Index.ets')}
def validate_hap(data,manifest):
 actual=D.verify_hap(data,manifest);members=D.read_zip_members(data);module=D.read_json(members['module.json'])['module']
 if manifest['bundleName']!=BUNDLE or module.get('requestPermissions') or module.get('extensionAbilities'):raise ValueError('实际HAP含非批准bundle/权限/扩展')
 if not members.get('ets/modules.abc'):raise ValueError('实际ArkTS字节码缺失')
 return actual

def verify_staged_fixture(project,fixture):
 for relative,expected in fixture['fixtureSources'].items():
  if relative=='media-lock.json':continue
  p=project/relative
  if p.is_symlink() or not p.is_file() or E.sha(p)!=expected:raise ValueError('staging源码/媒体漂移')
 return True

def prepare_project(root,project,har):
 proof=validate_fixture(root)
 if project.exists():raise ValueError('拒绝复用旧device-package工程')
 shutil.copytree(root/'fixtures/device-smoke',project,ignore=shutil.ignore_patterns('media-lock.json','README.md'))
 def write(rel,value):(project/rel).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 write('build-profile.json5',{'app':{'signingConfigs':[],'products':[{'name':'default','targetSdkVersion':'6.0.2(22)','compatibleSdkVersion':'5.0.3(15)','runtimeOS':'HarmonyOS','buildOption':{'strictMode':{'caseSensitiveCheck':True,'useNormalizedOHMUrl':True}}}],'buildModeSet':[{'name':'debug'}]},'modules':[{'name':'entry','srcPath':'./entry','targets':[{'name':'default','applyToProducts':['default']}]}]})
 write('oh-package.json5',{'modelVersion':'6.0.2','dependencies':{},'devDependencies':{}})
 write('entry/build-profile.json5',{'apiType':'stageMode','buildOption':{},'targets':[{'name':'default'}]})
 write('entry/oh-package.json5',{'name':'entry','version':'1.0.0','dependencies':{'@vidall/player':'file:./libs/current.har'}})
 dest=project/'entry/libs/current.har';dest.parent.mkdir();shutil.copy2(har,dest)
 return proof

def cloud_source(context,target,env):
 if context.get('event')=='merge_group' and context.get('headSHA')!=context.get('checkoutSHA'):raise ValueError('merge_group必须使用已核组合checkout，不得补造PR head')
 if context.get('passed') is not True or context.get('trustedTarget') is not True or context.get('repository')!=D.REPOSITORY or context.get('checkoutSHA')!=env.get('GITHUB_SHA') or context.get('eventSHA')!=context['checkoutSHA']:raise ValueError('未绑定可信GitHub事件')
 source={'repositoryId':int(env.get('GITHUB_REPOSITORY_ID','0')),'repository':env.get('GITHUB_REPOSITORY'),'workflowPath':'.github/workflows/deveco26-pr82-gates.yml','workflowSHA':env.get('GITHUB_WORKFLOW_SHA'),'runId':int(env.get('GITHUB_RUN_ID','0')),'runAttempt':int(env.get('GITHUB_RUN_ATTEMPT','0')),'event':context['event'],'headSHA':context.get('headSHA',context['checkoutSHA']),'eventMergeSHA':context['checkoutSHA'],'sourceTreeSHA':context['treeSHA'],'sourceTrackedBytesSHA256':context['trackedBytesSHA256'],'toolchainLockSHA256':E.sha(HERE.parent/'deveco26/toolchain-lock.json'),'releaseSourceLockSHA256':E.sha(HERE.parent/'deveco26/release-source-lock.json'),'inputHAR_SHA256':target['artifact']['harSHA256']}
 D.validate_source(source);return source

def manifest_for(hap,source,libraries,fixture):
 return {'schemaVersion':1,'source':source,'hap':{'path':'device-unsigned.hap','bytes':hap.stat().st_size,'sha256':E.sha(hap)},'bundleName':BUNDLE,'moduleName':'entry','abilityName':'EntryAbility','api':D.API,'libraries':libraries,'media':fixture['media'],'test':{'mode':'normal-local-smoke','entrySourceSHA256':fixture['entrySourceSHA256'],'privateNasAllowed':False,'freshSessionRequired':True}}
def emit_bundle(hap,manifest,out):
 if out.exists():raise ValueError('拒绝覆盖已准备device制品')
 D.validate_source(manifest['source'])
 if manifest.get('hap')!={'path':'device-unsigned.hap','bytes':hap.stat().st_size,'sha256':E.sha(hap)}:raise ValueError('manifest未绑定实际HAP')
 validate_hap(hap.read_bytes(),manifest);out.mkdir(parents=True)
 shutil.copy2(hap,out/'device-unsigned.hap');(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 # GitHub upload-artifact后产生的ID/ZIP摘要只放外部审批，不回写这里。
 return {'manifestSHA256':E.sha(out/'manifest.json'),'unsignedHAP_SHA256':E.sha(out/'device-unsigned.hap'),'members':['manifest.json','device-unsigned.hap'],'uploadPerformed':False}

def proof(result,source,target):
 try:
  expected=target['artifact'];artifact=result['artifact'];prepared=result['prepared'];manifest=result['manifestSource'];D.validate_source(manifest)
  return result.get('passed') is True and result.get('localOnly') is False and result.get('signed') is False and result.get('deviceVerified') is False and result.get('sourceBefore')==source==result.get('sourceAfter') and result.get('inputHAR')==expected['harSHA256'] and result.get('buildExit')==0 and type(result.get('buildExit')) is int and artifact.get('passed') is True and artifact.get('libraries')==expected['libraries'] and artifact.get('api')==target['api'] and E.hash_valid(artifact.get('hapSHA256')) and result.get('dependency',{}).get('passed') is True and result['dependency'].get('installedLibraries')==expected['libraries'] and result.get('cleanup',{}).get('passed') is True and result.get('fixture')==validate_fixture(ROOT) and prepared.get('unsignedHAP_SHA256')==artifact['hapSHA256'] and E.hash_valid(prepared.get('manifestSHA256')) and prepared.get('members')==['manifest.json','device-unsigned.hap'] and prepared.get('uploadPerformed') is False and manifest['eventMergeSHA']==source['checkoutSHA'] and manifest['sourceTreeSHA']==source['treeSHA'] and manifest['sourceTrackedBytesSHA256']==source['trackedBytesSHA256'] and manifest['inputHAR_SHA256']==expected['harSHA256'] and manifest['toolchainLockSHA256']==E.sha(HERE.parent/'deveco26/toolchain-lock.json') and manifest['releaseSourceLockSHA256']==E.sha(HERE.parent/'deveco26/release-source-lock.json')
 except (KeyError,TypeError,ValueError,OSError):return False

def execute(root,out,studio,wrapper,common,local=False):
 root=root.resolve();out=out.resolve();work=out/'work';work.mkdir(parents=True,exist_ok=True);project=out/'device-package/project';rows=[];child=None
 result={'passed':False,'signed':False,'deviceVerified':False,'uploaded':False,'localOnly':local,'commands':rows,'formalArtifactAllowed':False}
 try:
  source=E.CONTEXT.snapshot(root);context=json.loads((work/'context.json').read_text());target=json.loads((work/'evaluation-result.json').read_text());expected={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']}
  if target.get('passed') is not True or source!=expected or target.get('sourceBefore')!=source or target.get('sourceAfter')!=source:raise ValueError('设备包与target不是同一源码')
  result['sourceBefore']=source;hars=list((root/'packages/vidall-player/build/default/outputs/deveco26').glob('*.har'))
  if len(hars)!=1:raise ValueError('当前HAR不唯一')
  har=hars[0];C.verify_har_digest(har,target['artifact']['harSHA256']);result['inputHAR']=target['artifact']['harSHA256'];libraries=target['artifact']['libraries']
  lock=json.loads((HERE.parent/'deveco26/toolchain-lock.json').read_text());result['toolchain']=C.verify_consumer_toolchain(studio,wrapper,common,lock)
  child=E.child_environment(dict(os.environ),studio/'Contents/tools/node/bin/node',studio,out/'device-package')
  fixture=prepare_project(root,project,har);result['fixture']=fixture;dest=project/'entry/libs/current.har';C.verify_har_digest(dest,result['inputHAR'])
  for name,args in [('device-clean',['build','clean']),('device-build',['build','--modules','entry@default'])]:
   output=E.TARGET.command(name,[studio/'Contents/tools/node/bin/node',wrapper,*args],project,child,work,rows,1200);selected,_=E.TARGET.selected_studio(output)
   if Path(selected).resolve()!=studio.resolve():raise ValueError('设备包混用SDK')
   if name=='device-clean' and list((project/'entry/build').rglob('*.hap')):raise ValueError('设备包clean残留HAP')
  result['buildExit']=rows[-1]['exit']
  haps=list((project/'entry/build/default/outputs/default').glob('*-unsigned.hap'))
  if len(haps)!=1:raise ValueError('unsigned设备HAP不唯一')
  hap=haps[0];result['dependency']=C.installed_identity(project,libraries,dest);result['artifact']=C.verify_hap(hap,libraries)
  manifest=manifest_for(hap,source if local else cloud_source(context,target,os.environ),libraries,fixture);validate_hap(hap.read_bytes(),manifest)
  if local:
   prepared=out/'device-package/prepared';prepared.mkdir(exist_ok=False);shutil.copy2(hap,prepared/'device-unsigned.hap');manifest['localOnly']=True;(prepared/'local-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');result['prepared']={'localOnly':True,'unsignedHAP_SHA256':E.sha(hap),'externalApprovalAllowed':False}
  else:
   result['manifestSource']=manifest['source'];result['prepared']=emit_bundle(hap,manifest,out/'device-package/unsigned-artifact')
  verify_staged_fixture(project,fixture)
  if validate_fixture(root)!=fixture:raise ValueError('fixture构建期间漂移')
  C.verify_har_digest(har,result['inputHAR']);C.verify_har_digest(dest,result['inputHAR']);result.update(sourceAfter=E.CONTEXT.assert_snapshot(root,source),passed=True)
 except Exception as error:result.update(errorType=type(error).__name__,error=E.redact(str(error)))
 finally:
  if child is not None and project.is_dir():
   try:result['cleanup']=C.stop_project(project,child,studio,work,rows,'device-package')
   except Exception as error:result.update(passed=False,cleanup={'passed':False,'errorType':type(error).__name__})
 (work/'device-package-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--studio',type=Path,required=True);p.add_argument('--wrapper',type=Path,required=True);p.add_argument('--common',type=Path,required=True);p.add_argument('--local',action='store_true');a=p.parse_args();r=execute(ROOT,a.out,a.studio.resolve(),a.wrapper.resolve(),a.common.resolve(),a.local);print(json.dumps({'passed':r['passed'],'signed':False,'deviceVerified':False}));raise SystemExit(0 if r['passed'] else 1)
