"""恢复核心输入只消费锁定 SDK；篡改、越界或失败均不得留下交付目录。"""
import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sp = importlib.util.spec_from_file_location('recovery_input', ROOT/'native/scripts/prepare-host-recovery-input.py')
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def row(p, rel): return {'path':rel,'size':p.stat().st_size,'sha256':sha(p)}
class Inputs(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.repo=self.root/'repo';self.repo.mkdir();self.deps=self.root/'deps';self.deps.mkdir();self.mpv=self.root/'mpv';self.mpv.mkdir();self.sdk=self.root/'sdk';self.sdk.mkdir()
  (self.mpv/'a.c').write_text('old\n');(self.deps/'license').write_text('license\n')
  (self.sdk/'lib').mkdir();(self.sdk/'lib/new.so').write_bytes(b'unchanged-sdk');(self.sdk/'lib/pkgconfig').mkdir();(self.sdk/'lib/pkgconfig/a.pc').write_text('prefix=/sealed/sdk\n')
  base={'relocations':[], 'files':[row(self.mpv/'a.c','sources/mpv/a.c'),row(self.deps/'license','license'),{'path':'ffmpeg/lib/old.so','size':1,'sha256':'unused-old-sdk'}]}
  self.base=self.root/'baseline.json';self.base.write_text(json.dumps(base))
  sd={'files':[row(self.sdk/'lib/new.so','lib/new.so'),row(self.sdk/'lib/pkgconfig/a.pc','lib/pkgconfig/a.pc')]};(self.sdk/'manifest.json').write_text(json.dumps(sd))
  (self.repo/'change.patch').write_text('--- a/a.c\n+++ b/a.c\n@@ -1 +1 @@\n-old\n+new\n');(self.repo/'recovery.c').write_text('recovery\n')
  self.lock={'baselineManifestSHA256':sha(self.base),'ffmpegManifestSHA256':sha(self.sdk/'manifest.json'),'patches':[{'path':'change.patch','sha256':sha(self.repo/'change.patch')}],'addedSources':[{'path':'recovery.c','target':'common/recovery.c','sha256':sha(self.repo/'recovery.c')}]}
  self.output=self.root/'output'
 def prepare(self):return m.prepare(self.repo,self.lock,self.base,self.deps,self.mpv,self.sdk,self.output)
 def test_sdk_and_added_sources(self):
  self.prepare();self.assertEqual((self.output/'sources/mpv/a.c').read_text(),'new\n');self.assertEqual((self.mpv/'a.c').read_text(),'old\n')
  self.assertEqual((self.output/'sources/mpv/common/recovery.c').read_text(),'recovery\n')
  self.assertEqual((self.output/'ffmpeg/lib/new.so').read_bytes(),b'unchanged-sdk');self.assertFalse((self.output/'ffmpeg/lib/old.so').exists())
  index=json.loads((self.output/'package.json').read_text());self.assertEqual(index['relocations'],[{'from':'/sealed/sdk','to':'ffmpeg'}])
  files={p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()};self.assertEqual(files,{r['path'] for r in index['files']}|{'package.json'})
  for r in index['files']:self.assertEqual(sha(self.output/r['path']),r['sha256'])
  with self.assertRaises(FileExistsError):self.prepare()
 def test_sdk_version_symlink(self):
  (self.sdk/'lib/av.so').symlink_to('new.so')
  sdk_index=json.loads((self.sdk/'manifest.json').read_text())
  sdk_index['files'].append(row(self.sdk/'lib/av.so','lib/av.so'))
  (self.sdk/'manifest.json').write_text(json.dumps(sdk_index));self.lock['ffmpegManifestSHA256']=sha(self.sdk/'manifest.json')
  self.prepare();self.assertFalse((self.output/'ffmpeg/lib/av.so').is_symlink())
  self.assertEqual((self.output/'ffmpeg/lib/av.so').read_bytes(),b'unchanged-sdk')
 def test_tampered_sdk(self):
  (self.sdk/'lib/new.so').write_bytes(b'bad')
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse(self.output.exists())
 def test_tampered_patch(self):
  (self.repo/'change.patch').write_text('bad')
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse(self.output.exists())
 def test_bad_baseline(self):
  self.base.write_text('{}')
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse(self.output.exists())
 def test_path_escape(self):
  self.lock['addedSources'][0]['target']='../escape'
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse((self.root/'escape').exists());self.assertFalse(self.output.exists())
 def test_bad_added_source(self):
  (self.repo/'recovery.c').write_text('bad')
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse(self.output.exists())
if __name__=='__main__':unittest.main()
