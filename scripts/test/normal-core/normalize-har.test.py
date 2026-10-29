#!/usr/bin/env python3
"""HAR 规范化的先行契约：仅元数据可变，危险成员和内容变异必须被发现。"""
import gzip, hashlib, io, json, subprocess, sys, tarfile, tempfile, unittest
from pathlib import Path
TOOL=Path(__file__).with_name('normalize-har.py')
class NormalizeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def archive(self,name,rows,stamp=123,uid=501):
  p=self.root/name
  with p.open('wb') as raw,gzip.GzipFile(filename=name,mode='wb',fileobj=raw,mtime=stamp) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
   for entry in rows:
    path,data,*kind=entry;t=tarfile.TarInfo(path);t.uid=uid;t.gid=uid;t.uname='owner'+str(uid);t.gname='group'+str(uid);t.mtime=stamp;t.mode=0o640
    if kind:t.type=kind[0];t.linkname='package/a'
    else:t.size=len(data)
    tar.addfile(t,io.BytesIO(data) if t.isreg() else None)
  return p
 def call(self,*args):return subprocess.run([sys.executable,'-B',str(TOOL),*map(str,args)],capture_output=True,text=True)
 def norm(self,p,name):
  target=self.root/name;r=self.call('normalize',p,target);self.assertEqual(r.returncode,0,r.stderr);return target
 def test_metadata_and_order_equal(self):
  a=self.archive('a.har',[('package/a',b'one'),('package/b',b'two')],1,1)
  b=self.archive('b.har',[('package/b',b'two'),('package/a',b'one')],9999,999)
  originals=[a.read_bytes(),b.read_bytes()];na=self.norm(a,'na.har');nb=self.norm(b,'nb.har')
  self.assertEqual(na.read_bytes(),nb.read_bytes());self.assertEqual(originals,[a.read_bytes(),b.read_bytes()])
 def test_content_change_and_comparison_fail(self):
  a=self.norm(self.archive('a.har',[('package/a',b'one')]),'na.har')
  b=self.norm(self.archive('b.har',[('package/a',b'ONE')]),'nb.har')
  self.assertNotEqual(hashlib.sha256(a.read_bytes()).digest(),hashlib.sha256(b.read_bytes()).digest())
  report=self.root/'report.json';r=self.call('compare',a,b,'--report',report)
  self.assertEqual(r.returncode,1,r.stderr);self.assertFalse(json.loads(report.read_text())['passed'])
 def test_paths_bytes_and_mode_preserved(self):
  p=self.norm(self.archive('a.har',[('./package/中文.bin',bytes(range(256)))]),'n.har')
  with tarfile.open(p) as t:
   m=t.getmembers()[0];self.assertEqual(m.name,'./package/中文.bin');self.assertEqual(m.mode,0o640);self.assertEqual(t.extractfile(m).read(),bytes(range(256)))
 def test_identical_comparison(self):
  a=self.norm(self.archive('a.har',[('package/a',b'a')]),'n.har');r=self.call('compare',a,a,'--report',self.root/'report.json');self.assertEqual(r.returncode,0,r.stderr)
 def reject(self,rows):
  source=self.archive('a.har',rows);target=self.root/'n.har';r=self.call('normalize',source,target);self.assertEqual(r.returncode,2,r.stderr);self.assertIn('HAR 门禁拒绝',r.stderr);self.assertFalse(target.exists())
 def test_traversal(self):self.reject([('package/../escape',b'a')])
 def test_absolute(self):self.reject([('/escape',b'a')])
 def test_windows_path(self):self.reject([('C:\\escape',b'a')])
 def test_duplicate(self):self.reject([('package/a',b'a'),('package/a',b'b')])
 def test_alias_duplicate(self):self.reject([('package/a',b'a'),('./package/a',b'b')])
 def test_symlink(self):self.reject([('package/link',b'',tarfile.SYMTYPE)])
 def test_hardlink(self):self.reject([('package/link',b'',tarfile.LNKTYPE)])
 def test_special(self):self.reject([('package/device',b'',tarfile.CHRTYPE)])
 def test_existing_output_untouched(self):
  a=self.archive('a.har',[('package/a',b'a')]);target=self.root/'n.har';target.write_bytes(b'protected');r=self.call('normalize',a,target);self.assertNotEqual(r.returncode,0);self.assertEqual(target.read_bytes(),b'protected')
if __name__=='__main__':unittest.main()
