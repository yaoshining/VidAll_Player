#!/usr/bin/env python3
"""CI 交付门禁：先覆盖真实 tar 成员、输入漂移和事件身份失败场景。"""
import hashlib,importlib.util,io,json,tarfile,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class Audit(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.required={'libs/arm64-v8a/libmpv.so':hashlib.sha256(b'core').hexdigest()}
 def archive(self,rows):
  p=self.root/'test.har'
  with tarfile.open(p,'w:gz') as t:
   for name,data in rows:
    info=tarfile.TarInfo('package/'+name);info.size=len(data);t.addfile(info,io.BytesIO(data))
  return p
 def test_expected_archive(self):
  p=self.archive([('libs/arm64-v8a/libmpv.so',b'core')]);self.assertEqual(audit.inspect_har(p,self.required,set(self.required))['libraries'][0]['sha256'],self.required['libs/arm64-v8a/libmpv.so'])
 def test_changed_missing_and_extra_input(self):
  for rows in [[('libs/arm64-v8a/libmpv.so',b'new core')],[],[('libs/arm64-v8a/libmpv.so',b'core'),('libs/arm64-v8a/libavcodec.so.62',b'ffmpeg')]]:
   with self.assertRaises(ValueError):audit.inspect_har(self.archive(rows),self.required,set(self.required))
 def test_duplicate_member_rejected(self):
  with self.assertRaises(ValueError):audit.inspect_har(self.archive([('libs/arm64-v8a/libmpv.so',b'core')]*2),self.required,set(self.required))
 def test_ci_identity(self):
  env={'GITHUB_ACTIONS':'true','GITHUB_SHA':'a'*40,'GITHUB_REPOSITORY':'yaoshining/VidAll_Player','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}
  self.assertEqual(audit.ci_identity(env,'a'*40)['sourceCommit'],'a'*40)
  for change in [{'GITHUB_ACTIONS':'false'},{'GITHUB_SHA':'b'*40},{'GITHUB_RUN_ID':''},{'GITHUB_REPOSITORY':'other/repo'}]:
   with self.assertRaises(ValueError):audit.ci_identity({**env,**change},'a'*40)
if __name__=='__main__':unittest.main()
