#!/usr/bin/env python3
"""当前producer交付不可借清单自报或新标签替换；变更需独立交付审查。"""
import importlib.util,unittest,tempfile,json,hashlib
from pathlib import Path
P=Path(__file__).with_name('producer-input.py')
def mod():
 s=importlib.util.spec_from_file_location('producer010',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Tests(unittest.TestCase):
 def test_current_frozen(self):
  m=mod();self.assertTrue(m.verify(m.ROOT,m.load_lock())['passed'])
 def test_current_mpv_matches_ci_and_no_experimental_delivery_claim(self):
  m=mod();lock=m.load_lock();e=lock['acceptanceEvidence']
  ci=json.loads((m.ROOT/e['ciEvidence']).read_text())
  device=json.loads((m.ROOT/e['deviceEvidence']).read_text())
  self.assertEqual(ci['sourceCommit'],e['productionSourceCommit'])
  self.assertEqual(ci['runUrl'],e['ciRunUrl'])
  self.assertEqual(device['sourceCommit'],e['productionSourceCommit'])
  self.assertEqual(lock['files']['arm64-v8a/libmpv.so'],ci['libraries']['package/libs/arm64-v8a/libmpv.so'])
  self.assertFalse(lock['producerLatestNormalFullCloudRebuildVerified'])
  self.assertFalse(lock['formalArtifactAllowed'])
  self.assertFalse(e['ffmpegUpdated'])
  compile=json.loads((m.ROOT/'release/inputs/004-normal-core/provenance/normal-compile-binding.json').read_text())
  self.assertFalse(compile['observedMacros']['EXPERIMENT'])
  self.assertFalse(compile['observedMacros']['DIAGNOSTIC'])
 def test_wrong_manifest_library_and_path(self):
  m=mod()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base=root/'release/inputs/004-normal-core';(base/'arm64-v8a').mkdir(parents=True);(base/'manifest.json').write_text('{}');(base/'arm64-v8a/libx.so').write_bytes(b'abc')
   files=['manifest.json','arm64-v8a/libx.so'];lock={'acceptedDelivery':'test','files':{n:m.sha(base/n) for n in files}}
   result=m.verify(root,lock)
   self.assertTrue(result['passed'])
   self.assertEqual(result['acceptedDelivery'],lock['acceptedDelivery'])
   for target in files:
    p=base/target;old=p.read_bytes();p.write_bytes(old+b'changed')
    with self.assertRaises(ValueError):m.verify(root,lock)
    p.write_bytes(old)
   for path in ['../escape','/absolute']:
    bad={'files':{path:'a'*64}}
    with self.assertRaises(ValueError):m.verify(root,bad)
   p=base/'arm64-v8a/libx.so';p.unlink();p.symlink_to(base/'manifest.json')
   with self.assertRaises(ValueError):m.verify(root,lock)
if __name__=='__main__':unittest.main()
