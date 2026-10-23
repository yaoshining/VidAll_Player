#!/usr/bin/env python3
"""官方工具归档必须先验摘要；这里只测下载/提取边界，不冒充表达式解析。"""
import hashlib,importlib.util,io,tarfile,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent

def module():
 p=HERE/'ci-schema.py';assert p.exists(),'schema入口尚未实现'
 spec=importlib.util.spec_from_file_location('schema',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class SchemaArchive(unittest.TestCase):
 def test_good_wrong_digest_missing_or_link(self):
  m=module()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for mode in ['normal','wrong-hash','missing','link','duplicate']:
    archive=root/(mode+'.tgz')
    with tarfile.open(archive,'w:gz') as t:
     item=tarfile.TarInfo('other' if mode=='missing' else 'actionlint');data=b'fake tool';item.size=len(data)
     if mode=='link':item.type=tarfile.SYMTYPE;item.linkname='/outside';item.size=0
     t.addfile(item,io.BytesIO(data) if mode!='link' else None)
     if mode=='duplicate':t.addfile(item,io.BytesIO(data))
    expected='0'*64 if mode=='wrong-hash' else hashlib.sha256(archive.read_bytes()).hexdigest()
    if mode=='normal':self.assertEqual(m.extract_verified(archive,expected,root/'tool').read_bytes(),b'fake tool')
    else:
     with self.assertRaises(ValueError):m.extract_verified(archive,expected,root/'tool-bad')
 def test_platform_is_explicit(self):
  m=module();self.assertEqual(m.platform_key('Darwin','arm64'),'darwin_arm64');self.assertEqual(m.platform_key('Linux','x86_64'),'linux_amd64')
  with self.assertRaises(ValueError):m.platform_key('Windows','AMD64')
if __name__=='__main__':unittest.main()
