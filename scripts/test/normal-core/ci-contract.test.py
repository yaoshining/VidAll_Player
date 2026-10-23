#!/usr/bin/env python3
"""真实 CI helper/子进程回归；工具与HAR夹具不冒充HarmonyOS构建。"""
import importlib.util,sys,unittest,tempfile,subprocess,json,os,hashlib,tarfile,io
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent

def module(name):
 p=HERE/(name+'.py')
 if not p.exists():raise AssertionError('新增CI入口尚未实现：'+p.name)
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL,text=True).strip()
 def repo(self):
  self.git('init','-b','main');self.git('config','user.name','CI Test');self.git('config','user.email','ci@example.invalid')
  (self.root/'a').write_text('base');self.git('add','.');self.git('commit','-m','base');base=self.git('rev-parse','HEAD');self.git('checkout','-b','feature');(self.root/'b').write_text('head');self.git('add','.');self.git('commit','-m','head');head=self.git('rev-parse','HEAD');self.git('checkout','main');self.git('merge','--no-ff','feature','-m','merge');merge=self.git('rev-parse','HEAD');return base,head,merge
 def context(self):
  base,head,merge=self.repo();env={'GITHUB_EVENT_NAME':'pull_request','GITHUB_SHA':merge,'GITHUB_REF':'refs/pull/82/merge','GITHUB_REPOSITORY':'test/repo'};event={'pull_request':{'base':{'sha':base,'ref':'main','repo':{'full_name':'test/repo'}},'head':{'sha':head,'repo':{'full_name':'test/repo'}}}};return env,event
 def test_pr_real_merge(self):
  m=module('ci-context');env,event=self.context();r=m.verify(self.root,env,event);self.assertTrue(r['passed']);self.assertEqual(r['checkoutSHA'],env['GITHUB_SHA'])
 def test_wrong_checkout(self):
  m=module('ci-context');env,event=self.context();env['GITHUB_SHA']='0'*40
  with self.assertRaises(ValueError):m.verify(self.root,env,event)
 def test_wrong_pr_parent(self):
  m=module('ci-context');env,event=self.context();event['pull_request']['head']['sha']='f'*40
  with self.assertRaises(ValueError):m.verify(self.root,env,event)
 def test_head_checkout_rejected(self):
  m=module('ci-context');env,event=self.context();env['GITHUB_SHA']=event['pull_request']['head']['sha'];self.git('checkout',env['GITHUB_SHA'])
  with self.assertRaises(ValueError):m.verify(self.root,env,event)
 def test_push_manual_merge_group(self):
  m=module('ci-context');base,head,merge=self.repo()
  for kind in ['push','workflow_dispatch','merge_group']:
   env={'GITHUB_EVENT_NAME':kind,'GITHUB_SHA':merge,'GITHUB_REF':'refs/heads/main','GITHUB_REPOSITORY':'test/repo'};event={'merge_group':{'head_sha':merge,'base_sha':base,'base_ref':'refs/heads/main'}} if kind=='merge_group' else {}
   self.assertTrue(m.verify(self.root,env,event)['passed'])
 def test_unknown_event_missing_fields(self):
  m=module('ci-context');env,event=self.context();event['pull_request']['base'].pop('sha')
  with self.assertRaises((ValueError,KeyError)):m.verify(self.root,env,event)
  env['GITHUB_EVENT_NAME']='pull_request_target'
  with self.assertRaises(ValueError):m.verify(self.root,env,event)
 def test_fork_is_explicit(self):
  m=module('ci-context');env,event=self.context();event['pull_request']['head']['repo']['full_name']='foreign/fork';self.assertFalse(m.verify(self.root,env,event)['trustedTarget'])
 def test_real_command_failure_keeps_output(self):
  m=module('ci-target');work=self.root/'work';work.mkdir();rows=[]
  with self.assertRaises(RuntimeError):m.command('build',[sys.executable,'-c','import sys;print("specific-build-failure",flush=True);sys.exit(9)'],self.root,dict(os.environ),work,rows,5)
  self.assertEqual(rows[0]['exit'],9);self.assertIn('specific-build-failure',(work/'build.log').read_text())
 def test_real_command_timeout_keeps_output(self):
  m=module('ci-target');work=self.root/'work';work.mkdir();rows=[]
  with self.assertRaises(RuntimeError):m.command('build',[sys.executable,'-c','import time;print("before-timeout",flush=True);time.sleep(2)'],self.root,dict(os.environ),work,rows,.1)
  self.assertEqual(rows[0]['exit'],'timeout');self.assertIn('before-timeout',(work/'build.log').read_text())
 def test_aggregate_skipped_failure_cancelled(self):
  m=module('ci-evidence')
  self.assertTrue(m.verdict({'host-contracts':{'result':'success'},'target-har':{'result':'success'}}))
  for result in ['skipped','failure','cancelled','']:
   self.assertFalse(m.verdict({'host-contracts':{'result':'success'},'target-har':{'result':result}}))
  self.assertFalse(m.verdict({}))
 def test_public_failure_collection(self):
  m=module('ci-evidence');out=self.root/'evidence';(out/'work').mkdir(parents=True);(out/'work/failure.log').write_text('failure at /Users/private/secret/file\n');m.finish(out,{'build':{'outcome':'failure'}},'target');text=(out/'public/failure.log').read_text();self.assertNotIn('/Users/',text);self.assertFalse(json.loads((out/'public/ci-status.json').read_text())['stepsPassed'])
 def test_missing_failure_records_not_green(self):
  m=module('ci-evidence');out=self.root/'evidence';m.finish(out,{},'host');self.assertFalse(json.loads((out/'public/ci-status.json').read_text())['stepsPassed'])
 def test_sdk_ambiguity_or_absent(self):
  m=module('ci-target')
  for text in ['', '[DEBUG] [ToolProvider] Using auto → /one (1)\n[DEBUG] [ToolProvider] Using auto → /two (2)']:
   with self.assertRaises(ValueError):m.selected_studio(text)
  self.assertEqual(m.selected_studio('[DEBUG] [ToolProvider] Using auto → /test/App.app (6.1.1.268)')[0],'/test/App.app')
 def sdk(self):
  native=self.root/'native';(native/'llvm/bin').mkdir(parents=True);(native/'sysroot').mkdir();(native/'oh-uni-package.json').write_text(json.dumps({'apiVersion':'24','version':'6.1.1.115'}));files={}
  for n in ['clang','llvm-nm','llvm-readelf']:
   p=native/'llvm/bin'/n;p.write_text('tool-'+n);p.chmod(0o755);files['llvm/bin/'+n]=sha(p)
  files['oh-uni-package.json']=sha(native/'oh-uni-package.json');return native,{'apiVersion':'24','version':'6.1.1.115','files':files}
 def test_sdk_hash_and_api_drift(self):
  m=module('ci-target');native,lock=self.sdk();self.assertTrue(m.sdk_identity(native,lock)['passed']);(native/'llvm/bin/clang').write_text('drift')
  with self.assertRaises(ValueError):m.sdk_identity(native,lock)
 def test_sdk_missing_or_wrong_api(self):
  m=module('ci-target');native,lock=self.sdk();(native/'oh-uni-package.json').write_text(json.dumps({'apiVersion':'22','version':'6.1.1.115'}))
  with self.assertRaises(ValueError):m.sdk_identity(native,lock)
  (native/'llvm/bin/llvm-nm').unlink()
  with self.assertRaises(ValueError):m.sdk_identity(native,lock)
 def test_har_wrong_missing_bridge_and_core(self):
  m=module('ci-target');base=self.root/'inputs';base.mkdir();names=['libmpv.so','libavcodec.so.62','libavformat.so.62','libavfilter.so.11','libavutil.so.60','libswresample.so.6','libswscale.so.9','libc++_shared.so'];rows=[]
  for n in names:
   p=base/n;p.write_bytes(('core-'+n).encode());rows.append({'path':n,'sha256':sha(p)})
  bridge=bytearray(64);bridge[:6]=b'\x7fELF\x02\x01';bridge[18:20]=(183).to_bytes(2,'little');bp=self.root/'bridge';bp.write_bytes(bridge)
  for mode in ['normal','wrong-core','missing-bridge','wrong-bridge','duplicate']:
   har=self.root/(mode+'.har')
   with tarfile.open(har,'w:gz') as t:
    for row in rows:
     data=(base/row['path']).read_bytes();data=b'wrong' if mode=='wrong-core' and row['path']=='libmpv.so' else data;i=tarfile.TarInfo('package/libs/arm64-v8a/'+row['path']);i.size=len(data);t.addfile(i,io.BytesIO(data))
    if mode=='duplicate':
     data=b'duplicate';i=tarfile.TarInfo('package/libs/arm64-v8a/libmpv.so');i.size=len(data);t.addfile(i,io.BytesIO(data))
    if mode!='missing-bridge':
     data=b'wrong' if mode=='wrong-bridge' else bytes(bridge);i=tarfile.TarInfo('package/libs/arm64-v8a/libvidall_player_native.so');i.size=len(data);t.addfile(i,io.BytesIO(data))
   if mode=='normal':self.assertTrue(m.verify_har(har,rows,bp)['passed'])
   else:
    with self.assertRaises(ValueError):m.verify_har(har,rows,bp)
 def test_input_missing_wrong_hash(self):
  m=module('ci-target');p=self.root/'lib';p.write_bytes(b'a');rows=[{'path':'lib','sha256':sha(p)}];m.input_bytes(self.root,rows);p.write_bytes(b'b')
  with self.assertRaises(ValueError):m.input_bytes(self.root,rows)
  p.unlink()
  with self.assertRaises(ValueError):m.input_bytes(self.root,rows)

 def test_tracked_dirty_rejected(self):
  m=module('ci-context');env,event=self.context();(self.root/'a').write_text('dirty')
  with self.assertRaises(ValueError):m.verify(self.root,env,event)
 def test_snapshot_detects_post_build_drift(self):
  m=module('ci-context');self.repo();before=m.snapshot(self.root);(self.root/'a').write_text('changed')
  with self.assertRaises(ValueError):m.assert_snapshot(self.root,before)
 def test_sdk_compile_command_drift(self):
  m=module('ci-target');native,lock=self.sdk();source=self.root/'unit.cpp';source.write_text('unit');cc=self.root/'compile_commands.json';compiler=native/'llvm/bin/clang';command=str(compiler)+' --sysroot='+str(native/'sysroot')+' -c '+str(source)
  cc.write_text(json.dumps([{'file':str(source),'command':command,'directory':str(self.root)}]));self.assertTrue(m.compiled_sources(self.root,cc,native))
  cc.write_text(json.dumps([{'file':str(source),'command':'/wrong/clang --sysroot=/wrong/sysroot -c '+str(source),'directory':str(self.root)}]))
  with self.assertRaises(ValueError):m.compiled_sources(self.root,cc,native)
 def runner_fixture(self):
  m=module('ci-target');self.repo();base=self.root/'release/inputs/004-normal-core';base.mkdir(parents=True);libraries=[]
  for name in m.NAMES:
   p=base/name;p.write_text(name);libraries.append({'path':name,'sha256':sha(p)})
  (base/'manifest.json').write_text(json.dumps({'libraries':libraries}));audit=self.root/'scripts/audit';audit.mkdir(parents=True);(audit/'normal-core-verify.py').write_text('print("audit passed")')
  tools=self.root/'fake-tools';tools.mkdir();tool=tools/'devecocli';tool.write_text('#!'+sys.executable+'\nimport os,sys,time\nprint("fake-cli-run:"+" ".join(sys.argv[1:]),flush=True)\nmode=os.environ["TEST_MODE"]\nif mode=="timeout":time.sleep(5)\nif mode=="clean-fail" and "clean" in sys.argv:sys.exit(7)\nif mode=="build-fail" and "clean" not in sys.argv:sys.exit(9)\n');tool.chmod(0o755)
  self.git('add','.');self.git('commit','-m','fixture');return m,base,{**os.environ,'PATH':str(tools)+os.pathsep+os.environ['PATH']}
 def test_full_runner_failures(self):
  m,base,env=self.runner_fixture()
  for mode in ['clean-fail','build-fail','timeout','missing-har']:
   out=self.root/('evidence-'+mode);child={**env,'TEST_MODE':mode}
   with patch.object(m,'discover_sdk',return_value=(child,self.root/'native')):r=m.execute(self.root,out,child,timeout=1.5)
   self.assertFalse(r['passed'],mode);self.assertTrue((out/'work/target-result.json').is_file());self.assertIn('fake-cli-run',(out/'work/clean.log').read_text())
   if mode=='build-fail':self.assertEqual(r['commands'][-1]['exit'],9)
   if mode=='missing-har':self.assertIn('唯一HAR',r['error'])
 def test_full_runner_stale_compile_or_bridge_rejected(self):
  m,base,env=self.runner_fixture();child={**env,'TEST_MODE':'fake-success'}
  for name in ['packages/vidall-player/.cxx/default/default/debug/arm64-v8a/compile_commands.json','packages/vidall-player/build/default/intermediates/stripped_native_libs/default/arm64-v8a/libvidall_player_native.so']:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('stale')
   with patch.object(m,'discover_sdk',return_value=(child,self.root/'native')):r=m.execute(self.root,self.root/'evidence',child)
   self.assertFalse(r['passed']);self.assertIn('clean后',r['error']);self.assertNotIn('har-build',[c['name'] for c in r['commands']]);p.unlink()
 def test_full_runner_missing_input_before_clean(self):
  m,base,env=self.runner_fixture();(base/'libmpv.so').unlink();child={**env,'TEST_MODE':'fake-success'}
  with patch.object(m,'discover_sdk',return_value=(child,self.root/'native')):r=m.execute(self.root,self.root/'evidence',child)
  self.assertFalse(r['passed']);self.assertNotIn('clean',[c['name'] for c in r['commands']])
 def test_host_evidence_requires_suite_and_context(self):
  m=module('ci-evidence');out=self.root/'evidence';r=m.finish(out,{s:{'outcome':'success'} for s in ['context','dependencies','contracts','host']},'host');self.assertFalse(r['stepsPassed'])

 def test_host_finish_rejects_post_context_change(self):
  m=module('ci-evidence');identity=module('ci-context');self.repo();before=identity.snapshot(self.root);out=self.root/'evidence';(out/'work').mkdir(parents=True);(out/'suite/public').mkdir(parents=True)
  (out/'work/context.json').write_text(json.dumps({'passed':True,**before}));checks=[{'name':'c'+str(i),'passed':True,'exit':0,'expectedExit':0} for i in range(47)]
  (out/'suite/public/summary.json').write_text(json.dumps({'passed':True,'checks':checks}));(out/'suite/public/source-identities.json').write_text('{}')
  for c in checks:(out/'suite/public'/(c['name']+'.log')).write_text('PASS')
  (out/'suite/public/index.json').write_text('{}');steps={s:{'outcome':'success'} for s in ['context','dependencies','contracts','host']}
  with patch.object(m,'ROOT',self.root):
   self.assertTrue(m.finish(out,steps,'host')['stepsPassed']);self.assertIn('host/index.json',[r['path'] for r in json.loads((out/'public/index.json').read_text())['files']])
   (self.root/'a').write_text('dirty');self.assertFalse(m.finish(out,steps,'host')['stepsPassed']);self.git('checkout','--','a');self.git('commit','--allow-empty','-m','same tree new commit');self.assertFalse(m.finish(out,steps,'host')['stepsPassed'])

if __name__=='__main__':unittest.main()
