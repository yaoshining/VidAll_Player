#!/usr/bin/env python3
"""上传门禁的隔离负例，禁止二进制与私有路径意外进入证据包。"""
import importlib.util, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('public_gate',Path(__file__).with_name('check-public.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PublicGateTests(unittest.TestCase):
 def verify(self,name,content):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/name;p.write_bytes(content)
   return module.verify(Path(directory))
 def test_normal_text(self): self.assertFalse(self.verify('result.json',b'{"passed":true}'))
 def test_binary(self): self.assertTrue(self.verify('libmpv.so',b'\x7fELF'))
 def test_null_byte(self): self.assertTrue(self.verify('result.log',b'PASS\0'))
 def test_private_path(self): self.assertTrue(self.verify('result.log',b'/Users/test/private/signature'))
 def test_unknown_extension(self): self.assertTrue(self.verify('source-lock.toml',b'input'))
 def test_symlink(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);(p/'outside.log').write_text('PASS');(p/'alias.log').symlink_to(p/'outside.log')
   self.assertTrue(module.verify(p))
 def test_empty(self):
  with tempfile.TemporaryDirectory() as directory:self.assertTrue(module.verify(Path(directory)))
if __name__=='__main__':unittest.main()
