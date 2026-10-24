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
 def test_wrong_manifest_library_and_path(self):
  m=mod()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base=root/'release/inputs/004-normal-core';(base/'arm64-v8a').mkdir(parents=True);(base/'manifest.json').write_text('{}');(base/'arm64-v8a/libx.so').write_bytes(b'abc')
   files=['manifest.json','arm64-v8a/libx.so'];lock={'files':{n:m.sha(base/n) for n in files}}
   self.assertTrue(m.verify(root,lock)['passed'])
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
