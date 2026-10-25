#!/usr/bin/env python3
import copy,hashlib,importlib.util,io,json,pathlib,shutil,tempfile,unittest,zipfile
HERE=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('pack',HERE/'package.py');P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
sha=lambda b:hashlib.sha256(b).hexdigest()
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);shutil.copytree(P.ROOT/'fixtures/device-smoke',self.root/'fixtures/device-smoke');(self.root/'scripts/test/device-package').mkdir(parents=True);shutil.copy2(HERE/'generate_media.py',self.root/'scripts/test/device-package/generate_media.py')
 def tearDown(self):self.tmp.cleanup()
 def test_actual_fixture(self):self.assertTrue(P.validate_fixture(self.root)['passed'])
 def test_reject_private_network_backup_and_internal_import(self):
  fixture=self.root/'fixtures/device-smoke';module=fixture/'entry/src/main/module.json5';original=module.read_text()
  for key,value in [('requestPermissions',[{'name':'ohos.permission.INTERNET'}]),('extensionAbilities',[{'type':'backup'}])]:
   data=json.loads(original);data['module'][key]=value;module.write_text(json.dumps(data))
   with self.subTest(key=key),self.assertRaises(ValueError):P.validate_fixture(self.root)
   module.write_text(original)
  entry=fixture/'entry/src/main/ets/pages/Index.ets';old=entry.read_text()
  for extra in ["\nconst credentials = 'smb://private';", "\nimport native from 'libvidall_player_native.so';"]:
   entry.write_text(old+extra)
   with self.subTest(extra=extra),self.assertRaises(ValueError):P.validate_fixture(self.root)
  entry.write_text(old)
 def test_staged_fixture_drift(self):
  har=self.root/'input.har';har.write_bytes(b'test-har')
  project=self.root/'project';proof=P.prepare_project(self.root,project,har)
  P.verify_staged_fixture(project,proof)
  (project/'entry/src/main/ets/pages/Index.ets').write_text('changed')
  with self.assertRaises(ValueError):P.verify_staged_fixture(project,proof)
 def test_reject_extra_file(self):
  p=self.root/'fixtures/device-smoke/entry/src/main/resources/rawfile/private.json';p.write_text('{}')
  with self.assertRaises(ValueError):P.validate_fixture(self.root)
 def test_reject_bad_media(self):
  p=self.root/'fixtures/device-smoke/entry/src/main/resources/rawfile/test_video.mp4';p.write_bytes(p.read_bytes()+b'x')
  with self.assertRaises(ValueError):P.validate_fixture(self.root)
 def test_reject_missing_public_api(self):
  p=self.root/'fixtures/device-smoke/entry/src/main/ets/smoke/PlatformPort.ets';p.write_text(p.read_text().replace('initializePlayerRuntime','missingRuntime'))
  with self.assertRaises(ValueError):P.validate_fixture(self.root)
 def test_reject_symlink(self):
  p=self.root/'fixtures/device-smoke/unsafe';p.symlink_to('/tmp')
  with self.assertRaises(ValueError):P.validate_fixture(self.root)
 def manifest_hap(self,permission=False,wrong_lib=False,wrong_api=False):
  libs={n:sha(n.encode()) for n in P.D.LIBRARIES};media=b'synthetic';module={'app':{'bundleName':'com.yaoshining.vidalldeviceprobe',**P.D.API},'module':{'name':'entry','abilities':[{'name':'EntryAbility'}]}}
  if permission:module['module']['requestPermissions']=[{'name':'ohos.permission.INTERNET'}]
  if wrong_api:module['app']['minAPIVersion']=1
  contents={'module.json':json.dumps(module).encode(),'resources/rawfile/test_video.mp4':media,'ets/modules.abc':b'compiled'};contents.update({'libs/arm64-v8a/'+n:n.encode() for n in libs})
  if wrong_lib:contents['libs/arm64-v8a/libmpv.so']=b'wrong'
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   for n,v in contents.items():z.writestr(n,v)
  return {'bundleName':module['app']['bundleName'],'moduleName':'entry','abilityName':'EntryAbility','api':P.D.API,'libraries':libs,'media':{'path':'resources/rawfile/test_video.mp4','bytes':len(media),'sha256':sha(media),'generatorSHA256':'a'*64,'parameters':['fixed'],'origin':'generated-synthetic'},'test':{'mode':'normal-local-smoke','entrySourceSHA256':'b'*64,'privateNasAllowed':False,'freshSessionRequired':True}},out.getvalue()
 def test_actual_hap_policy(self):
  m,b=self.manifest_hap();self.assertEqual(P.validate_hap(b,m),m['libraries'])
  for args in [{'permission':True},{'wrong_lib':True},{'wrong_api':True}]:
   m,b=self.manifest_hap(**args)
   with self.subTest(args=args),self.assertRaises(ValueError):P.validate_hap(b,m)
 def test_wrong_manifest_hap_hash_rejected(self):
  m,b=self.manifest_hap();hap=self.root/'unsigned.hap';hap.write_bytes(b)
  m.update(schemaVersion=1,source=self.source(),hap={'path':'device-unsigned.hap','bytes':len(b),'sha256':'0'*64})
  with self.assertRaises(ValueError):P.emit_bundle(hap,m,self.root/'out')
 def source(self):
  return dict(repositoryId=1307243374,repository='yaoshining/VidAll_Player',workflowPath='.github/workflows/deveco26-pr82-gates.yml',workflowSHA='a'*40,runId=100,runAttempt=1,event='pull_request',headSHA='b'*40,eventMergeSHA='c'*40,sourceTreeSHA='d'*40,sourceTrackedBytesSHA256='e'*64,toolchainLockSHA256='f'*64,releaseSourceLockSHA256='1'*64,inputHAR_SHA256='2'*64)
 def test_bundle_exact_members_and_no_self_reference(self):
  m,b=self.manifest_hap();hap=self.root/'unsigned.hap';hap.write_bytes(b);m.update(schemaVersion=1,source=self.source(),hap={'path':'device-unsigned.hap','bytes':len(b),'sha256':sha(b)})
  r=P.emit_bundle(hap,m,self.root/'out');self.assertEqual(set(p.name for p in (self.root/'out').iterdir()),{'manifest.json','device-unsigned.hap'});self.assertFalse(r['uploadPerformed']);self.assertNotIn('artifactId',m)
  with self.assertRaises(ValueError):P.emit_bundle(hap,m,self.root/'out')
 def test_cloud_binding_failure(self):
  c=dict(passed=True,trustedTarget=True,repository='yaoshining/VidAll_Player',checkoutSHA='c'*40,eventSHA='c'*40,event='pull_request',headSHA='b'*40,treeSHA='d'*40,trackedBytesSHA256='e'*64)
  env=dict(GITHUB_SHA='c'*40,GITHUB_REPOSITORY_ID='1307243374',GITHUB_REPOSITORY='yaoshining/VidAll_Player',GITHUB_WORKFLOW_SHA='a'*40,GITHUB_RUN_ID='100',GITHUB_RUN_ATTEMPT='1')
  t={'artifact':{'harSHA256':'2'*64}};self.assertEqual(P.cloud_source(c,t,env)['eventMergeSHA'],'c'*40)
  for k,v in [('GITHUB_SHA','b'*40),('GITHUB_RUN_ID','0'),('GITHUB_REPOSITORY','other/repo'),('GITHUB_WORKFLOW_SHA','latest')]:
   wrong={**env,k:v}
   with self.subTest(field=k),self.assertRaises(ValueError):P.cloud_source(c,t,wrong)
 def test_merge_group_uses_actual_group_checkout(self):
  c=dict(passed=True,trustedTarget=True,repository='yaoshining/VidAll_Player',checkoutSHA='c'*40,eventSHA='c'*40,event='merge_group',headSHA='c'*40,baseSHA='b'*40,treeSHA='d'*40,trackedBytesSHA256='e'*64)
  env=dict(GITHUB_SHA='c'*40,GITHUB_REPOSITORY_ID='1307243374',GITHUB_REPOSITORY='yaoshining/VidAll_Player',GITHUB_WORKFLOW_SHA='a'*40,GITHUB_RUN_ID='100',GITHUB_RUN_ATTEMPT='1');target={'artifact':{'harSHA256':'2'*64}}
  source=P.cloud_source(c,target,env)
  self.assertEqual(source['event'],'merge_group');self.assertEqual(source['headSHA'],source['eventMergeSHA']);self.assertEqual(source['headSHA'],'c'*40)
  for change in [{'headSHA':'b'*40},{'headSHA':None},{'eventSHA':'b'*40},{'checkoutSHA':'b'*40}]:
   with self.subTest(change=change),self.assertRaises(ValueError):P.cloud_source({**c,**change},target,env)
 def test_result_proof(self):
  identity={'checkoutSHA':'c'*40,'treeSHA':'d'*40,'trackedBytesSHA256':'e'*64};libraries={n:'f'*64 for n in P.D.LIBRARIES};api={'compileSdkVersion':'26.0.0.105',**P.D.API};target={'artifact':{'harSHA256':'2'*64,'libraries':libraries},'api':api};source=self.source();source['toolchainLockSHA256']=P.E.sha(P.HERE.parent/'deveco26/toolchain-lock.json');source['releaseSourceLockSHA256']=P.E.sha(P.HERE.parent/'deveco26/release-source-lock.json')
  good=dict(passed=True,localOnly=False,signed=False,deviceVerified=False,sourceBefore=identity,sourceAfter=identity,inputHAR='2'*64,buildExit=0,artifact=dict(passed=True,libraries=libraries,api=api,hapSHA256='3'*64),dependency=dict(passed=True,installedLibraries=libraries),cleanup=dict(passed=True),fixture=P.validate_fixture(P.ROOT),prepared=dict(unsignedHAP_SHA256='3'*64,manifestSHA256='4'*64,members=['manifest.json','device-unsigned.hap'],uploadPerformed=False),manifestSource=source)
  self.assertTrue(P.proof(good,identity,target))
  for field,value in [('localOnly',True),('signed',True),('deviceVerified',True),('buildExit',True),('buildExit',1),('inputHAR','0'*64),('cleanup',{'passed':False}),('fixture',{}),('prepared',{}),('manifestSource',{}),('artifact',{'passed':True})]:
   wrong=copy.deepcopy(good);wrong[field]=value
   with self.subTest(field=field,value=value):self.assertFalse(P.proof(wrong,identity,target))
if __name__=='__main__':unittest.main()
