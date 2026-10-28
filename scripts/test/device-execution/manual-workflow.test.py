#!/usr/bin/env python3
"""手动准备/只读收证真实函数TDD；合成载荷和宿主替身不冒充设备执行。"""
import copy, importlib.util, json, os, sys, tempfile, unittest, io, zipfile, struct, subprocess
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
F=module('controller_fixture','controller.test.py')
M=module('manual_workflow','manual-workflow.py')
def encoded(x):return (json.dumps(x,sort_keys=True)+'\n').encode()
def sha(x):return F.sha(x)
class Tests(unittest.TestCase):
 def setUp(self):
  self.f=F.Tests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root.resolve()
  self.f.bundle='com.yaoshining.vidalldeviceprobe';self.f.manifest['bundleName']=self.f.bundle
  self.f.members['module.json']=encoded({'app':{'bundleName':self.f.bundle,**self.f.manifest['api']},'module':{'name':'entry','abilities':[{'name':'EntryAbility'}]}})
  self.f.source['workflowSHA']=self.f.source['eventMergeSHA'];self.f.repack()
  self.req={'schemaVersion':1,'mode':'prepare','source':self.f.source,'artifactId':456,'zipSHA256':sha(self.f.artifact.read_bytes()),'manifestSHA256':sha(encoded(self.f.manifest)),'hapSHA256':self.f.manifest['hap']['sha256']}
  # 控制器fixture的manifest序列化为紧凑格式，使用实际归档成员摘要。
  self.req['manifestSHA256']=sha(F.C.read_zip_members(self.f.artifact.read_bytes())['manifest.json'])
  self.api={
   'actions/runs/123/attempts/2':{'id':123,'run_attempt':2,'status':'completed','conclusion':'success','event':'pull_request','head_sha':'b'*40,'path':'.github/workflows/deveco26-pr82-gates.yml','repository':{'id':1307243374,'full_name':'yaoshining/VidAll_Player'},'head_repository':{'id':1307243374},'pull_requests':[{'head':{'sha':'b'*40},'base':{'sha':'9'*40}}]},
   'actions/artifacts/456':{'id':456,'name':'device-unsigned-'+('c'*40)+'-2','expired':False,'digest':'sha256:'+self.req['zipSHA256'],'size_in_bytes':self.f.artifact.stat().st_size,'workflow_run':{'id':123,'head_sha':'b'*40,'repository_id':1307243374,'head_repository_id':1307243374}},
   'git/commits/'+('c'*40):{'sha':'c'*40,'tree':{'sha':'d'*40},'parents':[{'sha':'9'*40},{'sha':'b'*40}]}}
  self.calls=[]
 def get(self,path):self.calls.append(path);return copy.deepcopy(self.api[path])
 def prepare(self):return M.prepare(self.req,self.get,lambda _:self.f.artifact.read_bytes())
 def setup_collect(self):
  self.state=self.root/'state';self.state.mkdir(mode=0o700);(self.state/'device.lock').touch(mode=0o600)
  self.receipts=self.root/'receipts';self.receipts.mkdir(mode=0o700)
  self.prepared=self.prepare();raw=encoded(self.prepared);self.psha=sha(raw);(self.receipts/(self.psha+'.json')).write_bytes(raw);(self.receipts/(self.psha+'.json')).chmod(0o600)
  self.nonce='a'*32;binding={'nonce':self.nonce,'bundle':self.f.bundle,'unsignedHapSHA256':self.req['hapSHA256'],'pid':123,'processStartTicks':20,'startedAtMs':1000}
  self.cleanup={'confirmed':True,'appSelfCleanup':'confirmed','failedChecks':[],'checks':{k:True for k in M.CLEANUP_CHECKS}}
  self.journal={'status':'complete','binding':binding,'installed':{'installedPayloadVerified':True},'cleanup':self.cleanup}
  self.smoke={'schemaVersion':1,'status':'passed','binding':binding,'approvalSHA256':'5'*64,'controllerSHA256':'6'*64,'scenarioPassed':True,'deviceVerified':True,'formalArtifactAllowed':False,'installedPayloadVerified':True,'signatureVerified':True,'signatureStatus':'verified','signature':{'signatureVerified':True,'payloadEqual':True,'derivedPagesVerified':True,'unsignedHAP_SHA256':self.req['hapSHA256'],'signedHAP_SHA256':'7'*64,'membersCompared':19},'cleanup':self.cleanup,'events':{'count':3,'truncated':False,'rows':[{'seq':1,'event':'session-start','bindingMismatch':False,'elapsedMs':0},{'seq':2,'event':'keep-screen','value':'false','bindingMismatch':False,'elapsedMs':30000},{'seq':3,'event':'session-end','value':'passed','bindingMismatch':False,'elapsedMs':30001}]},'cleanupCommandHistory':[]}
  for name in ['connection','device-id','packages','pid','ability','window']:
   row={'name':name,'phase':'post-uninstall','exitCode':0,'timedOut':False,'interrupted':False,'stderrEmpty':True,'checks':{'passed':True}}
   if name=='window':row['windowEvidence']={'code':'ok','parsePassed':True,'commandPassed':True,'absenceConfirmed':True,'reportedTotal':43,'observedRows':43}
   self.smoke['cleanupCommandHistory'].append(row)
  self.ledger={'nonces':[self.nonce]};self.collect_request={'schemaVersion':1,'mode':'collect','nonce':self.nonce,'preparedSHA256':self.psha,'journalSHA256':'0'*64,'ledgerSHA256':'0'*64,'smokeSHA256':'0'*64,'executionApprovalSHA256':'5'*64,'controllerSHA256':'6'*64}
  self.write_state()
 def write_state(self):
  for name,obj,key in [('journal.json',self.journal,'journalSHA256'),('used-nonces.json',self.ledger,'ledgerSHA256'),('smoke-'+self.nonce+'.json',self.smoke,'smokeSHA256')]:
   raw=encoded(obj);(self.state/name).write_bytes(raw);(self.state/name).chmod(0o600);self.collect_request[key]=sha(raw)
 def collect(self,host='1 /sbin/launchd\n'):return M.collect(self.collect_request,self.state,self.receipts,lambda:host)
 def test_prepare_reuses_exact_attempt_and_stays_unapproved(self):
  out=self.prepare();self.assertEqual(out['status'],'waiting-local-execution');self.assertFalse(out['deviceVerified']);self.assertFalse(out['executionAuthorized']);self.assertIn('actions/runs/123/attempts/2',self.calls);self.assertEqual(out['source'],self.f.source)
 def test_prepare_rejects_source_and_platform_mismatch(self):
  cases=[('actions/runs/123/attempts/2','run_attempt',3),('actions/runs/123/attempts/2','conclusion','failure'),('actions/runs/123/attempts/2','head_sha','0'*40),('actions/artifacts/456','expired',True),('actions/artifacts/456','digest','sha256:'+'0'*64),('actions/artifacts/456','name','wrong'),('actions/artifacts/456','size_in_bytes',1)]
  for path,k,v in cases:
   with self.subTest(path=path,key=k):
    old=self.api[path][k];self.api[path][k]=v
    with self.assertRaises(ValueError):self.prepare()
    self.api[path][k]=old
 def test_prepare_rejects_other_repo_and_parent_tree(self):
  for path,key,value in [('actions/runs/123/attempts/2','repository',{'id':1,'full_name':'other/repo'}),('actions/runs/123/attempts/2','head_repository',{'id':1}),('git/commits/'+('c'*40),'tree',{'sha':'0'*40}),('git/commits/'+('c'*40),'parents',[{'sha':'0'*40}])]:
   old=self.api[path][key];self.api[path][key]=value
   with self.assertRaises(ValueError):self.prepare()
   self.api[path][key]=old
 def test_prepare_rejects_hash_and_member_drift(self):
  for key in ['zipSHA256','manifestSHA256','hapSHA256']:
   old=self.req[key];self.req[key]='0'*64
   with self.assertRaises(ValueError):self.prepare()
   self.req[key]=old
 def test_request_digest_schema_and_modes(self):
  raw=encoded(self.req);self.assertEqual(M.request(raw,sha(raw),'prepare'),self.req)
  for data,digest,mode in [(raw,'0'*64,'prepare'),(raw,sha(raw),'collect'),(encoded({**self.req,'path':'/tmp/x'}),'','prepare')]:
   with self.assertRaises(ValueError):M.request(data,digest,mode)
  for value in ['../x',True,0]:
   bad={**self.req,'artifactId':value};raw=encoded(bad)
   with self.assertRaises(ValueError):M.request(raw,sha(raw),'prepare')
 def test_collect_pass_and_no_raw_data(self):
  self.setup_collect();self.smoke['private-extra']='DO_NOT_UPLOAD';self.write_state();out=self.collect();self.assertEqual(out['status'],'local-execution-evidence-verified');self.assertTrue(out['recordedDeviceVerified']);self.assertFalse(out['deviceCheckedNow']);self.assertNotIn('DO_NOT_UPLOAD',json.dumps(out));self.assertNotIn(self.nonce,json.dumps(out));self.assertFalse(out['executionAuthorized'])
 def test_collect_rejects_hash_or_request_drift(self):
  self.setup_collect()
  for k in ['preparedSHA256','journalSHA256','ledgerSHA256','smokeSHA256','executionApprovalSHA256','controllerSHA256']:
   old=self.collect_request[k];self.collect_request[k]='0'*64
   with self.assertRaises(ValueError):self.collect()
   self.collect_request[k]=old
 def test_collect_no_active_unknown_or_failed_green(self):
  self.setup_collect()
  for target,key,value in [(self.journal,'status','cleanup-unknown'),(self.smoke,'status','active'),(self.smoke,'signatureVerified',False),(self.smoke,'installedPayloadVerified',False),(self.smoke,'failure',{'code':'failed'}),(self.smoke,'deviceVerified',False)]:
   old=target.get(key);target[key]=value;self.write_state()
   with self.assertRaises(ValueError):self.collect()
   if old is None:target.pop(key)
   else:target[key]=old
  self.write_state()
  (self.state/'session-x').mkdir()
  with self.assertRaises(ValueError):self.collect()
  (self.state/'session-x').rmdir()
  for ps in ['', 'garbage', '2 python3 /x/imac.py --execute\n','2 java -jar hap-sign-tool.jar sign-app\n']:
   with self.assertRaises(ValueError):self.collect(ps)
 def test_collect_strict_post_window_and_history(self):
  self.setup_collect();w=self.smoke['cleanupCommandHistory'][-1]
  for key,value in [('phase','pre-uninstall'),('exitCode',1),('timedOut',True)]:
   old=w[key];w[key]=value;self.write_state()
   with self.assertRaises(ValueError):self.collect()
   w[key]=old
  w['windowEvidence']['observedRows']=42;self.write_state()
  with self.assertRaises(ValueError):self.collect()
  w['windowEvidence']['observedRows']=43;self.smoke['cleanupCommandHistory']*=6;self.write_state()
  with self.assertRaises(ValueError):self.collect()
 def test_collect_lease_and_path_guards(self):
  self.setup_collect()
  with F.C.DeviceLease(self.state/'device.lock'):
   with self.assertRaises(ValueError):self.collect()
  file=self.state/'journal.json';original=file.read_bytes();file.unlink();(self.root/'outside').write_bytes(original);file.symlink_to(self.root/'outside')
  with self.assertRaises(ValueError):self.collect()
 def test_collect_preserves_state_bytes(self):
  self.setup_collect();before={f.name:f.read_bytes() for f in self.state.iterdir() if f.is_file()};self.collect();after={f.name:f.read_bytes() for f in self.state.iterdir() if f.is_file()};self.assertEqual(before,after)
 def test_collect_rejects_foreign_nonce_and_missing_events(self):
  self.setup_collect();self.journal['binding']={**self.journal['binding'],'nonce':'b'*32};self.write_state()
  with self.assertRaises(ValueError):self.collect()
  self.journal['binding']=self.smoke['binding'];self.smoke['events']['rows'][-1]['value']='failed';self.write_state()
  with self.assertRaises(ValueError):self.collect()
 def bind_changed_hap(self,hap):
  self.f.manifest['hap']={'path':'device-unsigned.hap','bytes':len(hap),'sha256':sha(hap)}
  mb=encoded(self.f.manifest);out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('manifest.json',mb);z.writestr('device-unsigned.hap',hap)
  self.f.artifact.write_bytes(out.getvalue());self.req.update(zipSHA256=sha(out.getvalue()),manifestSHA256=sha(mb),hapSHA256=sha(hap))
  self.api['actions/artifacts/456'].update(digest='sha256:'+self.req['zipSHA256'],size_in_bytes=len(out.getvalue()))
 def test_unsigned_rejects_real_extra_block_and_member(self):
  hap=F.C.read_zip_members(self.f.artifact.read_bytes())['device-unsigned.hap']
  with zipfile.ZipFile(io.BytesIO(hap)) as z:offset=z.start_dir
  block=b'unsigned-must-not-contain-extra-signing-block'
  changed=bytearray(hap[:offset]+block+hap[offset:]);end=changed.rfind(b'PK\x05\x06');struct.pack_into('<I',changed,end+16,offset+len(block))
  self.bind_changed_hap(bytes(changed))
  with self.assertRaisesRegex(ValueError,'unsigned-signing-block'):self.prepare()
  out=io.BytesIO(hap)
  with zipfile.ZipFile(out,'a') as z:z.writestr('.pages.info',b'not-unsigned')
  self.bind_changed_hap(out.getvalue())
  with self.assertRaises(ValueError):self.prepare()
 def test_main_actual_prepare_and_context_rejection(self):
  raw=encoded(self.req);env={'GITHUB_REPOSITORY':M.REPO,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main','MANUAL_REQUEST':raw.decode(),'MANUAL_REQUEST_SHA256':sha(raw)}
  out=self.root/'cli-public'
  with patch.dict(os.environ,env,clear=True),patch.object(sys,'argv',['manual-workflow.py','prepare','--out',str(out)]),patch.object(M.GitHub,'get',side_effect=self.get),patch.object(M.GitHub,'download',return_value=self.f.artifact.read_bytes()):M.main()
  self.assertEqual(set(x.name for x in out.iterdir()),{'result.json'});self.assertFalse(json.loads((out/'result.json').read_bytes())['executionAuthorized'])
  for key,value in [('GITHUB_REF','refs/pull/82/merge'),('GITHUB_EVENT_NAME','push'),('GITHUB_REPOSITORY','other/repo')]:
   bad={**env,key:value}
   with patch.dict(os.environ,bad,clear=True),patch.object(sys,'argv',['manual-workflow.py','prepare','--out',str(self.root/'reject')]):
    with self.assertRaisesRegex(ValueError,'workflow-context'):M.main()
  extra=encoded({**self.req,'secret':'PRIVATE_SENTINEL'})
  run=subprocess.run([sys.executable,'-I','-B',str(HERE/'manual-workflow.py'),'prepare','--out',str(self.root/'reject')],env={**env,'MANUAL_REQUEST':extra.decode(),'MANUAL_REQUEST_SHA256':sha(extra)},capture_output=True,text=True)
  self.assertEqual(run.returncode,1);self.assertNotIn('PRIVATE_SENTINEL',run.stdout+run.stderr);self.assertFalse((self.root/'reject').exists())
 def test_main_collect_no_token_and_missing_cleanup_rejected(self):
  self.setup_collect();raw=encoded(self.collect_request);out=self.root/'collect-public'
  env={'GITHUB_REPOSITORY':M.REPO,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main','MANUAL_REQUEST':raw.decode(),'MANUAL_REQUEST_SHA256':sha(raw)}
  real=M.collect
  def local(r):
   self.assertNotIn('GH_TOKEN',os.environ);self.assertNotIn('GITHUB_TOKEN',os.environ)
   return real(r,self.state,self.receipts,lambda:'1 /sbin/launchd\n')
  with patch.dict(os.environ,env,clear=True),patch.object(sys,'platform','darwin'),patch.object(sys,'argv',['manual-workflow.py','collect','--out',str(out)]),patch.object(M,'collect',side_effect=local):M.main()
  self.assertFalse(json.loads((out/'result.json').read_bytes())['deviceCheckedNow'])
  self.cleanup['checks'].pop('package-absent');self.write_state()
  with self.assertRaisesRegex(ValueError,'recorded-cleanup'):self.collect()
if __name__=='__main__':unittest.main()
