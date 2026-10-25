#!/usr/bin/env python3
"""新组合必须检查consumer与事件身份；旧组合仅用于精确缺口RED，不修改旧语义。"""
import unittest,importlib.util,os,json,copy,tempfile
from unittest.mock import patch
from pathlib import Path
HERE=Path(__file__).resolve().parent
S='a'*40;IDENTITY={'checkoutSHA':S,'treeSHA':'b'*40,'trackedBytesSHA256':'c'*64}
def load(path):
 s=importlib.util.spec_from_file_location('subject',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Gates(unittest.TestCase):
 def setUp(self):
  if os.environ.get('GATES_BASELINE'):
   old=load(HERE.parent/'normal-core/ci-evidence.py');self.verdict=lambda n,s:old.verdict(n)
  else:self.m=load(HERE/'gates.py');self.verdict=self.m.verdict
 def good(self):
  summary={'passed':True,'targetPassed':True,'consumerPassed':True,'cleanupPassed':True,'apiNegativePassed':True,'sourceDownloadPassed':True,'hypiumPassed':True,'devicePackagePassed':True,'signerContractsPassed':True,'source':IDENTITY}
  return {'host-contracts':{'result':'success','outputs':{'source':json.dumps(IDENTITY)}},'target-har':{'result':'success','outputs':{'summary':json.dumps(summary)}}}
 def test_missing_consumer_evidence_rejected(self):self.assertFalse(self.verdict({'host-contracts':{'result':'success'},'target-har':{'result':'success'}},S))
 def test_complete(self):self.assertTrue(self.verdict(self.good(),S))
 def test_skipped_missing_cancelled(self):
  for result in ['skipped','cancelled','failure','']:
   n=self.good();n['target-har']['result']=result;self.assertFalse(self.verdict(n,S))
  self.assertFalse(self.verdict({'host-contracts':self.good()['host-contracts']},S))
 def test_old_sha_or_tree_rejected(self):
  self.assertFalse(self.verdict(self.good(),'d'*40))
  n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s['source']['treeSHA']='e'*40;n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_consumer_or_cleanup_false(self):
  for key in ['consumerPassed','targetPassed','cleanupPassed','apiNegativePassed','sourceDownloadPassed','hypiumPassed','devicePackagePassed','signerContractsPassed','passed']:
   n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s[key]=False;n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_missing_signer_contracts_rejected(self):
  n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s.pop('signerContractsPassed');n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_missing_device_package_rejected(self):
  n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s.pop('devicePackagePassed');n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_missing_hypium_rejected(self):
  n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s.pop('hypiumPassed');n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_missing_source_download_flag_rejected(self):
  n=self.good();s=json.loads(n['target-har']['outputs']['summary']);s.pop('sourceDownloadPassed');n['target-har']['outputs']['summary']=json.dumps(s);self.assertFalse(self.verdict(n,S))
 def test_finish_requires_source_download_proof(self):
  release=load(HERE.parent/'deveco26/release-source.py');lock,archive=release.load_inputs()
  good={'passed':True,'transportMode':'github-api','metadataVerified':True,'manifestVerified':True,'downloadVerified':True,'bootstrapPassed':True,'ownedInputCleaned':True,'sourceBefore':IDENTITY,'sourceAfter':IDENTITY,'sourceLockSHA256':release.config_sha(lock),'archiveLockSHA256':lock['archiveLockSHA256'],'sourceIdentity':release.expected_identity(lock),'archiveBytes':archive['archive']['bytes'],'archiveSHA256':archive['archive']['sha256']}
  with tempfile.TemporaryDirectory() as temp:
   out=Path(temp);work=out/'work';work.mkdir()
   libraries={n:'e'*64 for n in self.m.E.TARGET.NAMES|{'libvidall_player_native.so'}};api={'compileSdkVersion':'26.0.0.105','minAPIVersion':50003015,'targetAPIVersion':60002022};artifacts={'harSHA256':'f'*64,'libraries':libraries}
   common={'passed':True,'sourceBefore':IDENTITY,'sourceAfter':IDENTITY}
   records={'context.json':{**IDENTITY,'passed':True},'evaluation-result.json':{**common,'artifact':artifacts,'api':api},'consumer-result.json':{**common,'inputHAR':'f'*64,'libraries':artifacts['libraries'],'artifact':{'passed':True},'cleanup':{'passed':True}},'consumer-negative-result.json':{**common,'specificArkTSDiagnostic':True,'cleanup':{'passed':True}},'hypium-result.json':{**common,'inputHAR':'f'*64,'compiled':True,'signed':False,'executed':False,'cleanup':{'passed':True},'suiteNames':sorted(self.m.HYP.SUITES),'dependency':{'passed':True,'installedLibraries':libraries},'artifact':{'passed':True,'hapSHA256':'d'*64,'libraries':libraries,'api':api},'buildExit':0,'bytecodeSHA256':'1'*64,'bytecodeBytes':123,'moduleName':'entry_test','stagedSources':self.m.HYP.suite_sources(self.m.ROOT/'entry/src/ohosTest')},'cleanup-result.json':{'passed':True}}
   device_source={'repositoryId':1307243374,'repository':'yaoshining/VidAll_Player','workflowPath':'.github/workflows/deveco26-pr82-gates.yml','workflowSHA':S,'runId':123,'runAttempt':2,'event':'pull_request','headSHA':'d'*40,'eventMergeSHA':S,'sourceTreeSHA':IDENTITY['treeSHA'],'sourceTrackedBytesSHA256':IDENTITY['trackedBytesSHA256'],'toolchainLockSHA256':self.m.E.sha(HERE.parent/'deveco26/toolchain-lock.json'),'releaseSourceLockSHA256':self.m.E.sha(HERE.parent/'deveco26/release-source-lock.json'),'inputHAR_SHA256':'f'*64}
   records['device-package-result.json']={**common,'localOnly':False,'signed':False,'deviceVerified':False,'inputHAR':'f'*64,'buildExit':0,'artifact':{'passed':True,'libraries':libraries,'api':api,'hapSHA256':'3'*64},'dependency':{'passed':True,'installedLibraries':libraries},'cleanup':{'passed':True},'fixture':self.m.DEVICE.validate_fixture(self.m.ROOT),'prepared':{'unsignedHAP_SHA256':'3'*64,'manifestSHA256':'4'*64,'members':['manifest.json','device-unsigned.hap'],'uploadPerformed':False},'manifestSource':device_source}
   signer_source=self.m.E.sha(HERE.parent/'device-execution/signer-helper/ActualSigner.java');signer_jar='a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d'
   records['signer-helper-result.json']={'passed':True,'realHapVerified':False,'deviceVerified':False,'sourceSHA256':signer_source,'jarSHA256':signer_jar,'checks':[{'name':n,'passed':True} for n in ['actual-SID-twelve-cases','chain-membership-mutant-rejected','missing-arguments','wrong-hap-hash','actual-invalid-hap','symlink-input','wrong-jar','existing-output','separate-directory-class-reproducible']]}
   records['signer-helper-build.json']={'sourceSHA256':signer_source,'jarSHA256':signer_jar,'javaRelease':17,'classSHA256':'6'*64,'javacExecutableSHA256':'7'*64}
   for n,d in records.items():(work/n).write_text(json.dumps(d))
   steps={k:{'outcome':'success'} for k in ['context','trust','bootstrap','signer_contracts','runtime','target','api_negative','consumer','hypium','device_package','cleanup']}
   with patch.object(self.m.E.CONTEXT,'assert_snapshot',return_value=IDENTITY),patch.object(self.m.E,'publish',return_value={'passed':True}),patch.object(self.m,'output',lambda *a:None):
    for mode in ['missing','cleanup-false','old-lock','old-source','mock','positive']:
     path=work/'release-source-result.json'
     if path.exists():path.unlink()
     candidate=copy.deepcopy(good)
     if mode=='cleanup-false':candidate['ownedInputCleaned']=False
     elif mode=='old-lock':candidate['sourceLockSHA256']='0'*64
     elif mode=='old-source':candidate['sourceBefore']['checkoutSHA']='0'*40
     elif mode=='mock':candidate['transportMode']='injected-test-transport'
     if mode!='missing':path.write_text(json.dumps(candidate))
     with self.subTest(mode=mode):self.assertEqual(self.m.finish(out,steps)['passed'],mode=='positive')
 def test_host_missing_or_old_producer_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);work=out/'work';work.mkdir();native={'passed':True,'sourceBefore':IDENTITY,'sourceAfter':IDENTITY,'ctestNames':sorted(self.m.HOST.EXPECTED),'ctestPassed':14,'diagnosticsJS':['diagnostics-session','diagnostics-device']};producer={'passed':True,'sourceBefore':IDENTITY,'sourceAfter':IDENTITY,'files':self.m.PRODUCER.load_lock()['files'],'producerLatestNormalFullCloudRebuildVerified':False}
   (work/'legacy-native-result.json').write_text(json.dumps(native));self.assertFalse(self.m.host_proof(out,IDENTITY))
   for mode in ['pass','missing-source','wrong-files','false']:
    r=copy.deepcopy(producer)
    if mode=='missing-source':r.pop('sourceAfter')
    if mode=='wrong-files':r['files']={}
    if mode=='false':r['passed']=False
    (work/'producer-input-result.json').write_text(json.dumps(r));self.assertEqual(self.m.host_proof(out,IDENTITY),mode=='pass')
 def test_trust_exact_event_and_fork(self):
  c={**IDENTITY,'eventSHA':S,'event':'pull_request','passed':True,'trustedTarget':True,'repository':'yaoshining/VidAll_Player','headRepository':'yaoshining/VidAll_Player'}
  self.assertTrue(self.m.trusted(c,S));self.assertFalse(self.m.trusted(c,''));self.assertFalse(self.m.trusted(c,'d'*40))
  c['headRepository']='fork/Player';self.assertFalse(self.m.trusted(c,S))
if __name__=='__main__':unittest.main()
