#!/usr/bin/env python3
"""对实际接入清单运行正例及篡改/遗漏负例。"""
import importlib.util,json,tempfile,unittest,copy,shutil,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/audit/normal-core-verify.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
BASE=ROOT/'release/inputs/004-normal-core'
class BindingTests(unittest.TestCase):
 def test_host_recovery_exports_required(self):
  manifest=json.loads((BASE/'manifest.json').read_text())
  self.assertTrue({'mpv_host_recovery_api_version','mpv_host_recovery_generation','mpv_host_recovery_audio_pending','mpv_host_recovery_stop_audio','mpv_host_loadfile_async','mpv_host_fault_snapshot'}.issubset(manifest['requiredExports']['libmpv.so']))
 def test_host_recovery_input_binding(self):
  lock=json.loads((BASE/'provenance/source-lock.json').read_text())
  self.assertEqual(lock['hostRecovery']['inputLock'],'host-recovery-input.json')
  for item in json.loads((BASE/'provenance/host-recovery-input.json').read_text())['addedSources']:
   self.assertEqual(audit.sha(ROOT/item['path']),item['sha256'])
 def test_current_sdk_compilation_identity(self):
  compilation=json.loads((BASE/'provenance/normal-compile-binding.json').read_text())
  self.assertEqual(compilation['ffmpegInputManifestSHA256'],audit.FFMPEG_SDK_SHA)
  self.assertNotIn('ffmpegExplicitFlags',compilation)
 def test_actual_current_inputs(self):self.assertEqual(audit.verify(BASE),[])
 def mutated(self,change):
  d=json.loads((BASE/'manifest.json').read_text());change(d)
  return audit.verify(BASE,d)
 def test_current_ffmpeg_recovery_is_required(self):
  manifest=json.loads((BASE/'manifest.json').read_text())
  self.assertEqual(manifest.get('ffmpegRecovery'), 'provenance/ffmpeg-recovery-sdk.json')
 def test_missing_ffmpeg_recovery_binding(self):
  self.assertIn('FFmpeg 恢复 SDK 绑定缺失',self.mutated(lambda d:d.pop('ffmpegRecovery',None)))
 def test_wrong_ffmpeg_recovery_binding(self):
  self.assertTrue(self.mutated(lambda d:d.update(ffmpegRecovery='README.md')))
 def test_missing_ffmpeg_merge_binding(self):
  self.assertIn('FFmpeg 合并绑定缺失',self.mutated(lambda d:d.pop('ffmpegRecoveryMerge',None)))
 def test_old_ffmpeg_cannot_claim_recovery(self):
  def old(d):
   next(r for r in d['libraries'] if r['path'].endswith('libavcodec.so.62'))['sha256']='62331a15718a231f323ca0e8957272b7b1fc3eb48bf1e91d85a86760af15652a'
  self.assertTrue(any('FFmpeg 运行库未绑定恢复 SDK' in e for e in self.mutated(old)))
 def test_forged_ffmpeg_sdk(self):
  self.assertIn('FFmpeg 恢复 SDK 身份不匹配',self.changed_file('provenance/ffmpeg-recovery-sdk.json',lambda d:d.update(diagnosticInjection=True)))
 def test_forged_ffmpeg_merge(self):
  self.assertIn('FFmpeg 合并绑定身份不匹配',self.changed_file('provenance/ffmpeg-recovery-merge.json',lambda d:d.update(mergeCommit='0'*40)))
 def test_ffmpeg_cannot_inherit_mpv_trace(self):
  self.assertIn('FFmpeg 与 mpv 编译宏范围混淆',self.mutated(lambda d:d.update(ffmpegCompileDefinitions=['MP_OHCODEC_HANDOFF_TRACE=1'])))
 def test_missing_manifest(self):
  with tempfile.TemporaryDirectory() as t:self.assertIn('清单缺失',audit.verify(Path(t)))
 def test_legacy_interrupt_imports(self):
  # 模拟核心可用但只注册写入回调的旧版本。
  from unittest.mock import patch
  check_output=subprocess.check_output
  def without_interrupt(args, **kwargs):
   output=check_output(args, **kwargs)
   if '--undefined-only' in args:
    return '\n'.join(line for line in output.splitlines() if 'OH_AudioStreamBuilder_SetRendererCallback' not in line)
   return output
  with patch.object(audit.subprocess, 'check_output', side_effect=without_interrupt):
   self.assertIn('缺少旧系统中断注册接口',audit.verify(BASE))
 def test_wrong_library(self):self.assertTrue(self.mutated(lambda d:d['libraries'][0].update(sha256='0'*64)))
 def test_missing_library(self):self.assertTrue(self.mutated(lambda d:d['libraries'].pop()))
 def test_fault_macro(self):self.assertTrue(self.mutated(lambda d:d['compileDefinitions'].append('MP_OHCODEC_DIAGNOSTIC=1')))
 def test_missing_abi(self):self.assertTrue(self.mutated(lambda d:d['requiredExports']['libmpv.so'].append('mpv_missing_api_999')))
 def test_changed_header(self):self.assertTrue(self.mutated(lambda d:d['headers'][0].update(sha256='0'*64)))
 def test_formal_not_allowed(self):self.assertTrue(self.mutated(lambda d:d.update(formalArtifactAllowed=True)))
 def test_empty_abi(self):self.assertTrue(self.mutated(lambda d:d['requiredExports'].update({'libmpv.so':[]})))
 def test_claim_only_macro(self):self.assertTrue(self.mutated(lambda d:d.update(compileEvidence='README.md')))
 def changed_file(self,name,change):
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp)/'inputs';shutil.copytree(BASE,target,copy_function=os.symlink)
   p=target/name;d=json.loads(p.read_text());p.unlink();change(d);p.write_text(json.dumps(d))
   m=json.loads((BASE/'manifest.json').read_text())
   import hashlib
   for row in m['evidence']:
    if row['path']==name:row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
   return audit.verify(target,m)
 def test_forged_producer_binding(self):self.assertTrue(self.changed_file('provenance/normal-library-binding.json',lambda d:d.update({'libmpv.so':'0'*64})))
 def test_forged_compile_macro(self):self.assertTrue(self.changed_file('provenance/normal-compile-binding.json',lambda d:d['translationUnits'][0].update(command='clang -DMP_OHCODEC_HANDOFF_TEST=1')))
 def test_external_summary_errors(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'VIDALL_MPV_BUILD_ROOT':''}):
   target=Path(tmp)/'inputs';shutil.copytree(BASE,target,copy_function=os.symlink)
   summary=target/'provenance/mpv-run-summary.json';summary.unlink()
   for data in (None,'{', '{}', '{"runRoot":false}'):
    with self.subTest(data=data):
     if data is not None:summary.write_text(data)
     self.assertIn('无效或缺失的 mpv 构建目录证据',audit.verify(target,verify_external=True))
 def test_matching_static_archive(self):
  """来源锁的摘要与真实 ar 文件相符时，外部审计应接受该归档。"""
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'VIDALL_MPV_BUILD_ROOT':tmp}):
   target=Path(tmp)/'inputs';shutil.copytree(BASE,target,copy_function=os.symlink)
   lock_file=target/'provenance/source-lock.json'
   lock=json.loads(lock_file.read_text())
   archive=Path(tmp)/lock['staticLibplacebo']['path'].removeprefix('run/')
   archive.parent.mkdir(parents=True)
   member=Path(tmp)/'member';member.write_bytes(b'archive member')
   subprocess.run(['ar','rcs',str(archive),str(member)],check=True)
   lock['staticLibplacebo']['sha256']=audit.sha(archive)
   lock_file.unlink();lock_file.write_text(json.dumps(lock))
   digest=audit.sha(lock_file)
   manifest=json.loads((target/'manifest.json').read_text())
   next(row for row in manifest['evidence'] if row['path']=='provenance/source-lock.json')['sha256']=digest
   with patch.object(audit,'SOURCE_LOCK_SHA',digest):
    errors=audit.verify(target,manifest,verify_external=True)
   self.assertFalse(any('静态 libplacebo' in error or '来源锁身份' in error for error in errors),errors)
 def test_archive_disappears_during_read(self):
  from unittest.mock import patch
  actual=audit.sha
  def race(path):
   if path.name=='libplacebo.a':raise FileNotFoundError('archive disappeared')
   return actual(path)
  with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'VIDALL_MPV_BUILD_ROOT':tmp}):
   archive=Path(tmp)/'libplacebo/install/lib/libplacebo.a'
   archive.parent.mkdir(parents=True);archive.write_bytes(b'archive')
   with patch.object(audit,'sha',side_effect=race):
    self.assertTrue(any('静态 libplacebo' in err for err in audit.verify(BASE,verify_external=True)))
 def test_resource_hash(self):self.assertTrue(self.mutated(lambda d:d['resources'][0].update(sha256='0'*64)))
 def test_forged_source_lock(self):self.assertTrue(self.changed_file('provenance/source-lock.json',lambda d:d.update(exactReferences=[])))
 def test_missing_header(self):self.assertTrue(self.mutated(lambda d:d['headers'].clear()))
 def test_unrelated_resource_cannot_replace_smb_config(self):
  import hashlib
  row={'path':'README.md','sha256':hashlib.sha256((BASE/'README.md').read_bytes()).hexdigest()}
  self.assertTrue(self.mutated(lambda d:d.update(resources=[row])))
if __name__=='__main__':unittest.main()
