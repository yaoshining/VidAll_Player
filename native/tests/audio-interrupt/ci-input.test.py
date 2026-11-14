"""派生 CI 音频源必须与交付源一致，篡改或缺补丁不得形成绿色测试。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('audio_ci', ROOT/'native/scripts/prepare-audio-ci-input.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sha = lambda data: hashlib.sha256(data).hexdigest()

class AudioInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'player'
        self.source = self.root/'mpv'
        self.output = self.root/'output'
        self.source.mkdir(); self.repo.mkdir()
        self.file = 'audio/out/ao_ohaudio.c'
        original = self.source/self.file
        original.parent.mkdir(parents=True); original.write_text('before\n')
        subprocess.run(['git','init','-q',str(self.source)],check=True)
        subprocess.run(['git','-C',str(self.source),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.source),'-c','user.name=test','-c','user.email=test@example.invalid','commit','-qm','base'],check=True)
        commit = subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip()
        library = self.repo/'release/inputs/004-normal-core/arm64-v8a/libmpv.so'
        library.parent.mkdir(parents=True); library.write_bytes(b'core')
        patch = self.repo/'audio.patch'
        patch.write_text('diff --git a/'+self.file+' b/'+self.file+'\n--- a/'+self.file+'\n+++ b/'+self.file+'\n@@ -1 +1 @@\n-before\n+after\n')
        self.recovery = {'patches':[{'path':'audio.patch','sha256':sha(patch.read_bytes())}],'addedSources':[]}
        self.contract = {'upstreamCommit':commit,'mpvLibrarySHA256':sha(b'core'),'files':{self.file:{'baselineSHA256':sha(b'before\n'),'patchedSHA256':sha(b'after\n')}}}

    def prepare(self):
        return module.prepare(self.repo,self.source,self.output,self.contract,self.recovery)

    def test_exact_source_and_no_input_mutation(self):
        result = self.prepare()
        self.assertEqual((self.output/self.file).read_text(),'after\n')
        self.assertEqual((self.source/self.file).read_text(),'before\n')
        self.assertEqual(result['files'][self.file],sha(b'after\n'))
        with self.assertRaises(FileExistsError): self.prepare()

    def test_missing_patch_rejects_wrong_derived_source(self):
        self.recovery['patches'] = []
        with self.assertRaisesRegex(ValueError,'派生源码'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_baseline_tampering_rejected(self):
        (self.source/self.file).write_text('tampered\n')
        with self.assertRaisesRegex(ValueError,'基线源码'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_patch_tampering_rejected(self):
        (self.repo/'audio.patch').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'恢复输入'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_added_recovery_source_tampering_rejected(self):
        source = self.repo/'recovery.c';source.write_text('tampered')
        self.recovery['addedSources'] = [{'path':'recovery.c','sha256':sha(b'expected')}]
        with self.assertRaisesRegex(ValueError,'恢复输入'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_changed_delivery_rejected(self):
        self.contract['mpvLibrarySHA256'] = sha(b'other')
        with self.assertRaisesRegex(ValueError,'交付核心'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_wrong_checkout_rejected(self):
        self.contract['upstreamCommit'] = '0'*40
        with self.assertRaisesRegex(ValueError,'上游提交'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_path_escape_rejected(self):
        self.contract['files']['../outside'] = self.contract['files'][self.file]
        with self.assertRaisesRegex(ValueError,'越界'): self.prepare()
        self.assertFalse(self.output.exists())

    def test_workflow_runs_current_audio_regressions(self):
        workflow = (ROOT/'.github/workflows/test-player.yml').read_text()
        self.assertIn('prepare-audio-ci-input.py',workflow)
        self.assertIn('audio-interrupt/ci-input.test.py',workflow)
        self.assertIn('audio-interrupt/legacy-lifetime.test.py',workflow)
        for suite in ('audio-data','audio-control','audio-lifecycle','audio-clock'):
            self.assertIn('native/tests/host-survival/'+suite+'.test.py',workflow)
        self.assertNotIn('git -C .cache/mpv-interrupt apply',workflow)
        # pull_request 与 push(main) 都须触发，测试锁由 native/tests/** 覆盖。
        for path in ('native/patches/phase30/**','native/mpv/**','native/tests/**',
                     'native/scripts/prepare-audio-ci-input.py',
                     'release/inputs/004-normal-core/provenance/host-recovery-input.json',
                     'release/inputs/004-normal-core/arm64-v8a/libmpv.so'):
            self.assertEqual(workflow.count("      - '"+path+"'"),2,path)

if __name__ == '__main__': unittest.main()
