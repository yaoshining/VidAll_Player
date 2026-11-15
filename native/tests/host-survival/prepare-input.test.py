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
 def test_returned_audio_stop_patch_is_locked_and_applied(self):
  # 实际 0008 补丁必须经与正式构建相同的锁定入口应用，不能只测手改临时源码。
  name='audio/out/ao_ohaudio.c';audio=self.mpv/name;audio.parent.mkdir(parents=True)
  original='''static int stop_for_recovery(void *opaque)
{
    OH_AudioRenderer *renderer = opaque;
    OH_AudioStream_State state;
    if (OH_AudioRenderer_GetCurrentState(renderer, &state) != AUDIOSTREAM_SUCCESS) return -1;
    if (state == AUDIOSTREAM_STATE_PREPARED || state == AUDIOSTREAM_STATE_STOPPED) return 0;
    if (OH_AudioRenderer_Stop(renderer) != AUDIOSTREAM_SUCCESS) return -1;
    return OH_AudioRenderer_GetCurrentState(renderer, &state) == AUDIOSTREAM_SUCCESS &&
        state == AUDIOSTREAM_STATE_STOPPED ? 0 : -1;
}
'''
  audio.write_text(original);base=json.loads(self.base.read_text())
  base['files'].append(row(audio,'sources/mpv/'+name));self.base.write_text(json.dumps(base))
  self.lock['baselineManifestSHA256']=sha(self.base)
  rel='native/patches/phase30/0008-confirm-returned-audio-stop.patch'
  patch=self.repo/rel;patch.parent.mkdir(parents=True);patch.write_bytes((ROOT/rel).read_bytes())
  self.lock['patches'].append({'path':rel,'sha256':sha(patch)})
  self.prepare();derived=(self.output/'sources/mpv'/name).read_text()
  self.assertEqual(derived.count('OH_AudioRenderer_Stop(renderer);'),1)
  self.assertNotIn('if (OH_AudioRenderer_Stop(renderer)',derived)
  self.assertEqual(derived.count('OH_AudioRenderer_GetCurrentState(renderer, &state)'),2)
  self.assertEqual(audio.read_text(),original)
  index=json.loads((self.output/'package.json').read_text())
  self.assertEqual(index['hostRecovery']['patches'][-1],self.lock['patches'][-1])
  patch.write_text('tampered');self.output=self.root/'tampered-output'
  with self.assertRaisesRegex(ValueError,'输入摘要不匹配'):self.prepare()
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
