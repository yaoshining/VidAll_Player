#!/usr/bin/env python3
"""独立评估契约；网络使用本机HTTP替身，不冒充官方下载/目标构建。"""
import hashlib,importlib.util,json,tempfile,unittest,io,subprocess,os
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent

def module():
 s=importlib.util.spec_from_file_location('evaluation',HERE/'evaluate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Contract(unittest.TestCase):
 def setUp(self):
  self.m=module();self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
 def fixture(self):
  studio=self.root/'Studio.app';p=studio/'Contents/Resources/product-info.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'version':'26.0.0.851'}))
  node=studio/'Contents/tools/node/bin/node';node.parent.mkdir(parents=True);node.write_text('node')
  cli=self.root/'cli';cli.mkdir();(cli/'cli.js').write_text('wrapper');(cli/'common.js').write_text('common')
  lock={'studioVersion':'26.0.0.851','architecture':'arm64','studioFiles':{'Resources/product-info.json':self.m.sha(p),'tools/node/bin/node':self.m.sha(node)},'cli':{'version':'1.3.4','wrapperSHA256':self.m.sha(cli/'cli.js'),'commonSHA256':self.m.sha(cli/'common.js')}}
  return studio,cli,lock
 def test_identity_accepts_exact(self):
  s,c,l=self.fixture();self.assertTrue(self.m.preflight(s,c/'cli.js',c/'common.js',l,'arm64')['passed'])
 def test_architecture_rejected(self):
  s,c,l=self.fixture()
  with self.assertRaises(ValueError):self.m.preflight(s,c/'cli.js',c/'common.js',l,'x86_64')
 def test_tool_drift_rejected(self):
  s,c,l=self.fixture();(s/'Contents/tools/node/bin/node').write_text('changed')
  with self.assertRaises(ValueError):self.m.preflight(s,c/'cli.js',c/'common.js',l,'arm64')
 def test_missing_hash_rejected(self):
  s,c,l=self.fixture();l['studioFiles']['tools/node/bin/node']=''
  with self.assertRaises(ValueError):self.m.preflight(s,c/'cli.js',c/'common.js',l,'arm64')
 def test_cli_drift_rejected(self):
  s,c,l=self.fixture();(c/'common.js').write_text('1.2.0')
  with self.assertRaises(ValueError):self.m.preflight(s,c/'cli.js',c/'common.js',l,'arm64')
 def test_full_get_200(self):
  self.m.response_identity(200,{'Content-Length':'4'},4)
 def test_full_get_wrong_status(self):
  with self.assertRaises(ValueError):self.m.response_identity(206,{'Content-Length':'4'},4)
 def test_range_requires_exact_206(self):
  self.m.response_identity(206,{'Content-Length':'1','Content-Range':'bytes 0-0/4'},4,(0,0))
  with self.assertRaises(ValueError):self.m.response_identity(200,{'Content-Length':'4'},4,(0,0))
  with self.assertRaises(ValueError):self.m.response_identity(206,{'Content-Length':'1','Content-Range':'bytes 1-1/4'},4,(0,0))
 def test_truncated_or_wrong_hash(self):
  p=self.root/'cache';p.write_bytes(b'abcd');self.m.verify_file(p,4,hashlib.sha256(b'abcd').hexdigest())
  for size,h in [(5,hashlib.sha256(b'abcd').hexdigest()),(4,'0'*64),(4,'')]:
   with self.assertRaises(ValueError):self.m.verify_file(p,size,h)
 def test_product_api_metadata(self):
  self.m.api_metadata({'compileSdkVersion':'26.0.0.105','minAPIVersion':50003015,'targetAPIVersion':60002022})
  for k,v in [('minAPIVersion',26000000),('targetAPIVersion',26000000),('compileSdkVersion','6.1.1.115')]:
   j={'compileSdkVersion':'26.0.0.105','minAPIVersion':50003015,'targetAPIVersion':60002022};j[k]=v
   with self.assertRaises(ValueError):self.m.api_metadata(j)
 def test_hvigor_home_is_local_and_preserves_user_home(self):
  out=self.root/'out';out.mkdir()
  env=self.m.child_environment({'PATH':'/other','HOME':'/user-home','HVIGOR_USER_HOME':'/shared'},Path('/locked/node'),Path('/studio'),out)
  self.assertEqual(env['HVIGOR_USER_HOME'],str(out.resolve()/'hvigor-home'));self.assertEqual(env['HOME'],'/user-home')
 def test_hvigor_home_symlink_refused(self):
  out=self.root/'out';out.mkdir();(out/'hvigor-home').symlink_to(self.root/'shared')
  with self.assertRaises(ValueError):self.m.isolated_hvigor_home(out)
 def test_secret_sanitization(self):
  text=self.m.redact('failure https://vendor.test/file.zip?token=SECRET&sig=HIDDEN at /private/tmp/abc')
  self.assertNotIn('SECRET',text);self.assertNotIn('HIDDEN',text);self.assertNotIn('/private/tmp',text)
 def test_missing_result_not_success(self):
  self.assertFalse(self.m.result_passed({},True));self.assertFalse(self.m.result_passed({'passed':True},False));self.assertTrue(self.m.result_passed({'passed':True},True))
class Execution(Contract):
 def test_child_node_path(self):
  env=self.m.child_environment({'PATH':'/other/bin'},Path('/locked/Contents/tools/node/bin/node'),Path('/locked'),self.root/'environment')
  self.assertEqual(env['PATH'].split(os.pathsep)[0],'/locked/Contents/tools/node/bin')
  self.assertEqual(env['DEVECO_CLI_STUDIO_PATH'],'/locked')
 def test_cli_resolve_mismatch(self):
  self.m.validate_resolution({'execPath':'/locked/node','common':'/locked/common'},'/locked/node','/locked/common')
  for key in ['execPath','common']:
   data={'execPath':'/locked/node','common':'/locked/common'};data[key]='/other/file'
   with self.assertRaises(ValueError):self.m.validate_resolution(data,'/locked/node','/locked/common')
 def test_cli_debug_version(self):
  text='[DEBUG] [ToolProvider] Using DEVECO_CLI_STUDIO_PATH → /Applications/DevEco-Studio.app\n1.3.4\n'
  self.assertEqual(self.m.version_line(text),'1.3.4')
  for text in ['debug only','1.3.4\n1.3.4\n','1.3.4\n1.2.0\n']:
   with self.assertRaises(ValueError):self.m.version_line(text)
 def test_real_clean_failure_is_red_and_published(self):
  # 真正临时Git与外部进程失败；不是目标编译成功证据。
  studio,cli,lock=self.fixture()
  node=studio/'Contents/tools/node/bin/node'
  node.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo v24.14.1; exit 0; fi\nif [ "$2" = "--version" ]; then echo 1.3.4; exit 0; fi\necho injected-clean-failure\nexit 7\n');node.chmod(0o755)
  lock['studioFiles']['tools/node/bin/node']=self.m.sha(node);lock.update(nodeVersion='v24.14.1',native={'apiVersion':'26','version':'26.0.0.105','files':{}})
  native=studio/'Contents/sdk/default/openharmony/native';(native/'sysroot').mkdir(parents=True);(native/'oh-uni-package.json').write_text(json.dumps({'apiVersion':'26','version':'26.0.0.105'}))
  scripts=self.root/'scripts';scripts.mkdir();(scripts/'toolchain-lock.json').write_text(json.dumps(lock))
  repo=self.root/'repo';repo.mkdir();base=repo/'release/inputs/004-normal-core';base.mkdir(parents=True);libs=[]
  for name in self.m.TARGET.NAMES:
   p=base/name;p.write_text(name);libs.append({'path':name,'sha256':self.m.sha(p)})
  (base/'manifest.json').write_text(json.dumps({'libraries':libs}))
  for args in [('init','-q'),('add','.'),('-c','user.name=test','-c','user.email=test@example.test','commit','-qm','fixture')]:subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
  out=self.root/'out';(out/'work').mkdir(parents=True);before=self.m.CONTEXT.snapshot(repo);(out/'work/context.json').write_text(json.dumps({'passed':True,**before}))
  with patch.object(self.m,'HERE',scripts),patch.object(self.m.platform,'machine',return_value='arm64'),patch.object(self.m,'resolve_cli',return_value={'fixture':True}):
   result=self.m.execute(repo,out,studio,cli/'cli.js',cli/'common.js',dict(os.environ),5)
  self.assertFalse(result['passed']);self.assertEqual(result['commands'][-1]['name'],'clean');self.assertEqual(result['commands'][-1]['exit'],7)
  self.assertNotIn('har-build',[x['name'] for x in result['commands']]);self.assertFalse(self.m.publish(repo,out,True)['passed'])
  self.assertTrue((out/'public/clean.log').exists())
 def test_old_sdk_lock_rejects_new_metadata(self):
  native=self.root/'native';(native/'sysroot').mkdir(parents=True);(native/'oh-uni-package.json').write_text(json.dumps({'apiVersion':'26','version':'26.0.0.105'}))
  lock=json.loads((HERE.parent/'normal-core/ci-toolchain-lock.json').read_text())
  with self.assertRaisesRegex(ValueError,'API/version'):self.m.TARGET.sdk_identity(native,lock)
class LinkIdentity(unittest.TestCase):
 def setUp(self):self.m=module();self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
 def fixture(self):
  p=self.root/'build.ninja';runtime=self.root/'release/inputs/004-normal-core/arm64-v8a/libc++_shared.so';p.write_text('  LINK_FLAGS = -nostdlib++ -Wl,--no-undefined\n  LINK_LIBRARIES = -lace_napi.z '+str(runtime)+' -lm\n');return p
 def test_real_link_uses_fixed_runtime(self):self.assertTrue(self.m.link_identity(self.fixture(),self.root)['passed'])
 def test_sdk_automatic_link_rejected(self):
  p=self.fixture();p.write_text(p.read_text().replace('-nostdlib++',''))
  with self.assertRaises(ValueError):self.m.link_identity(p,self.root)
 def test_wrong_or_duplicate_runtime_rejected(self):
  for suffix in [' /SDK/libc++_shared.so',' -lc++_shared']:
   p=self.fixture();p.write_text(p.read_text().replace(' -lm',' -lm'+suffix))
   with self.assertRaises(ValueError):self.m.link_identity(p,self.root)
class NativeClean(unittest.TestCase):
 def setUp(self):
  self.m=module();self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)/'repo';self.root.mkdir()
  subprocess.run(['git','init','-q',str(self.root)],check=True)
  self.target=self.root/'packages/vidall-player/.cxx/default/deveco26'
 def test_owned_native_metadata_removed_default_preserved(self):
  self.target.mkdir(parents=True);(self.target/'compile_commands.json').write_text('old')
  old=self.target.parent/'default';old.mkdir();(old/'keep').write_text('preserve')
  r=self.m.clean_evaluation_native(self.root)
  self.assertEqual(r['removedFiles'],1);self.assertFalse(self.target.exists());self.assertEqual((old/'keep').read_text(),'preserve')
  self.assertEqual(self.m.clean_evaluation_native(self.root)['removedFiles'],0)
 def test_tracked_native_cache_refused(self):
  self.target.mkdir(parents=True);(self.target/'tracked').write_text('tracked')
  subprocess.run(['git','-C',str(self.root),'add','-f',str(self.target/'tracked')],check=True)
  with self.assertRaisesRegex(ValueError,'tracked'):self.m.clean_evaluation_native(self.root)
  self.assertTrue((self.target/'tracked').exists())
 def test_symlink_escape_refused(self):
  outside=Path(self.t.name)/'outside';outside.mkdir();self.target.parent.mkdir(parents=True);self.target.symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'符号链接'):self.m.clean_evaluation_native(self.root)
  self.assertTrue(outside.exists())
 def test_parent_symlink_refused(self):
  outside=Path(self.t.name)/'outside';outside.mkdir();(self.root/'packages').symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'符号链接'):self.m.clean_evaluation_native(self.root)
 def test_internal_symlink_refused(self):
  self.target.mkdir(parents=True);(self.target/'linked').symlink_to(self.root/'outside')
  with self.assertRaisesRegex(ValueError,'符号链接'):self.m.clean_evaluation_native(self.root)
if __name__=='__main__':unittest.main()
