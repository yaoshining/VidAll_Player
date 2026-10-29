#!/usr/bin/env python3
"""无签名Hypium必须复制完整测试并以真实产物证明编译，不能借签名存在冒充。"""
import importlib.util,json,tempfile,unittest,hashlib,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load():
 s=importlib.util.spec_from_file_location('hypium010',HERE/'hypium.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Tests(unittest.TestCase):
 def test_actual_stage_has_all_suites_and_no_signing(self):
  m=load()
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);har=d/'current.har';har.write_bytes(b'only-staging-test');p=d/'project';r=m.prepare_project(ROOT,p,har)
   original=ROOT/'entry/src/ohosTest'
   for f in original.rglob('*'):
    if f.is_file():self.assertEqual(f.read_bytes(),(p/'entry/src/ohosTest'/f.relative_to(original)).read_bytes())
   self.assertEqual(len(r['suites']),9);self.assertEqual(json.loads((p/'build-profile.json5').read_text())['app']['signingConfigs'],[])
   self.assertEqual(json.loads((p/'entry/oh-package.json5').read_text())['dependencies'],{'@vidall/player':'file:./libs/current.har'})
   self.assertEqual([x['name'] for x in json.loads((p/'build-profile.json5').read_text())['modules'][0]['targets']],['default']);self.assertFalse((p/'entry/src/main/cpp').exists());self.assertEqual(r['mode'],'compile-only-unsigned')
   with self.assertRaises(ValueError):m.prepare_project(ROOT,p,har)
 def test_actual_output_required(self):
  m=load()
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);hap=d/'test-unsigned.hap'
   with zipfile.ZipFile(hap,'w') as z:z.writestr('module.json',json.dumps({'module':{'name':'entry_test'}}));z.writestr('ets/modules.abc',b'actual-test-bytecode')
   self.assertTrue(m.compiled_output(hap)['compiled'])
   for entry in ['missing-bytecode','empty-bytecode','wrong-module']:
    with zipfile.ZipFile(hap,'w') as z:
     z.writestr('module.json',json.dumps({'module':{'name':'entry' if entry=='wrong-module' else 'entry_test'}}))
     if entry!='missing-bytecode':z.writestr('ets/modules.abc',b'' if entry=='empty-bytecode' else b'abc')
    with self.assertRaises(ValueError):m.compiled_output(hap)
 def test_failure_or_missing_fields_not_built(self):
  m=load();s={'checkoutSHA':'a'*40,'treeSHA':'b'*40,'trackedBytesSHA256':'c'*64};libs={n:'e'*64 for n in m.C.E.TARGET.NAMES|{'libvidall_player_native.so'}};api={'compileSdkVersion':'26.0.0.105','minAPIVersion':50003015,'targetAPIVersion':60002022};target={'artifact':{'harSHA256':'d'*64,'libraries':libs},'api':api}
  r={'passed':True,'sourceBefore':s,'sourceAfter':s,'inputHAR':'d'*64,'compiled':True,'signed':False,'executed':False,'cleanup':{'passed':True},'suiteNames':sorted(m.SUITES),'dependency':{'passed':True,'installedLibraries':libs},'artifact':{'passed':True,'hapSHA256':'f'*64,'libraries':libs,'api':api},'buildExit':0,'bytecodeSHA256':'1'*64,'bytecodeBytes':123,'moduleName':'entry_test','stagedSources':m.suite_sources(ROOT/'entry/src/ohosTest')}
  self.assertTrue(m.proof(r,s,target))
  for k in r:
   bad=dict(r);bad.pop(k);self.assertFalse(m.proof(bad,s,target),k)
  for k,v in [('buildExit',1),('compiled',False),('signed',True),('inputHAR','e'*64),('moduleName','entry'),('bytecodeSHA256',''),('bytecodeBytes',0),('stagedSources',{})]:
   bad=dict(r);bad[k]=v;self.assertFalse(m.proof(bad,s,target),k)
  for key,value in [('api',{}),('libraries',{}),('hapSHA256','')]:
   bad=dict(r);bad['artifact']={**r['artifact'],key:value};self.assertFalse(m.proof(bad,s,target),key)
if __name__=='__main__':unittest.main()
