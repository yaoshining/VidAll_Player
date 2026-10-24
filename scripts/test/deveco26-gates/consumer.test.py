#!/usr/bin/env python3
"""检查真实fixture根API；其余消费者输入/打包测试随接口RED加入。"""
import unittest,os,re,importlib.util,tempfile,json,zipfile,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
class Consumer(unittest.TestCase):
 def test_fixture_uses_normal_core_root_apis(self):
  name='libmpv-player-consumer/src/main' if os.environ.get('OLD_FIXTURE') else 'normal-core-consumer/entry/src/main'
  source=(ROOT/'fixtures'/name/'ets/pages/Index.ets').read_text()
  imported=re.search(r'import\s*\{([^}]+)\}\s*from\s*[\'"]@vidall/player[\'"]',source).group(1)
  for api in ['initializePlayerRuntime','onPlayerTerminal','getPlayerRuntimeStatus','createPlayer']:self.assertIn(api,imported)
  self.assertNotRegex(source,r"from ['\"](?:.*src/internal|libvidall_player_native)")
 def subject(self):
  s=importlib.util.spec_from_file_location('consumer',Path(__file__).with_name('consumer.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
 def hap_fixture(self,missing=None,extra=None,duplicate=False,api=50003015):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);p=Path(t.name)/'app-unsigned.hap';libs={n:hashlib.sha256(n.encode()).hexdigest() for n in ['libmpv.so','libavcodec.so.62','libavfilter.so.11','libavformat.so.62','libavutil.so.60','libswscale.so.9','libswresample.so.6','libc++_shared.so','libvidall_player_native.so']}
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('module.json',json.dumps({'app':{'compileSdkVersion':'26.0.0.105','targetAPIVersion':60002022,'minAPIVersion':api}}))
   for n in libs:
    if n!=missing:z.writestr('libs/arm64-v8a/'+n,n.encode())
   if extra:z.writestr('libs/arm64-v8a/'+extra,b'extra')
   if duplicate:z.writestr('libs/arm64-v8a/libmpv.so',b'wrong')
  return p,libs
 def test_hap_exact_nine_libraries(self):
  p,libs=self.hap_fixture();self.assertTrue(self.subject().verify_hap(p,libs)['passed'])
 def test_hap_missing_extra_duplicate(self):
  for options in [{'missing':'libmpv.so'},{'extra':'libwrong.so'},{'duplicate':True}]:
   p,libs=self.hap_fixture(**options)
   with self.assertRaises(ValueError):self.subject().verify_hap(p,libs)
 def test_hap_bridge_or_api_wrong(self):
  p,libs=self.hap_fixture();libs['libvidall_player_native.so']='0'*64
  with self.assertRaises(ValueError):self.subject().verify_hap(p,libs)
  p,libs=self.hap_fixture(api=60002022)
  with self.assertRaises(ValueError):self.subject().verify_hap(p,libs)
 def test_bound_har_rejects_stale_hash(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);p=Path(t.name)/'one.har';p.write_bytes(b'current')
  with self.assertRaises(ValueError):self.subject().verify_har_digest(p,'0'*64)
 def test_resolution_rejects_source_old_cache(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name);har=root/'entry/libs/current.har';har.parent.mkdir(parents=True);har.write_bytes(b'har')
  good={'packages':{'@vidall/player@libs/current.har':{'name':'@vidall/player','resolved':'libs/current.har','registryType':'local'}}}
  self.assertTrue(self.subject().resolution_lock(root/'entry',har,good)['passed'])
  for path in ['../../packages/vidall-player','libs/old.har','/tmp/old-cache.har']:
   good['packages']['@vidall/player@libs/current.har']['resolved']=path
   with self.assertRaises(ValueError):self.subject().resolution_lock(root/'entry',har,good)
 def test_negative_requires_specific_arkts_diagnostic(self):
  m=self.subject();message="ERROR ArkTS: Module '@vidall/player' has no exported member 'initializePlayerRuntime'."
  self.assertTrue(m.missing_api_diagnostic(message,1))
  for text,code in [('npm network error',1),(message,0),(message,'timeout'),("has no exported member 'otherAPI'",1)]:self.assertFalse(m.missing_api_diagnostic(text,code))
 def test_actual_host_architecture_rejected(self):
  from unittest.mock import patch
  m=self.subject()
  with patch.object(m.platform,'machine',return_value='x86_64'):
   with self.assertRaises(ValueError):m.verify_consumer_toolchain(Path('/not-read'),Path('/not-read'),Path('/not-read'),{'architecture':'arm64'})
 def test_registry_project_and_pid(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);home=Path(t.name)/'home';p=home/'daemon/cache/daemon-sec.json';p.parent.mkdir(parents=True);project=Path(t.name)/'project';project.mkdir()
  p.write_text(json.dumps({'ours':{'pid':12,'cwdPath':str(project)},'other':{'pid':13,'cwdPath':str(Path(t.name)/'else')}}))
  self.assertEqual(self.subject().owned_pids(home,project),{12})
  with self.assertRaises(ValueError):self.subject().B.stopped_pids('Stopped daemon pid 13.',{12})
  p.write_text(json.dumps({'ours':{'pid':-1,'cwdPath':str(project)}}))
  with self.assertRaises(ValueError):self.subject().owned_pids(home,project)
if __name__=='__main__':unittest.main()

