"""独立派生输入时不能静默跳过补丁，失败不能留下半成品。"""
import importlib.util
import json
import os
from unittest.mock import patch
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'native/scripts/prepare-normal-mpv-input.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)

class InputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.src = self.root / 'input'
        self.rel = 'sources/mpv/audio.c'
        self.file = self.src / self.rel
        self.file.parent.mkdir(parents=True)
        self.file.write_text('old\n')
        self.index = self.src / 'package.json'
        self.index.write_text(self.manifest())
        patch_file = self.root / 'fix.patch'
        patch_file.write_text('--- a/audio.c\n+++ b/audio.c\n@@ -1 +1 @@\n-old\n+new\n')
        paths = patch.multiple(prepare, ROOT=self.root, SOURCE_LOCK=self.root / 'lock.json')
        paths.start()
        self.addCleanup(paths.stop)
        base = prepare.digest(self.index)
        self.file.write_text('new\n')
        expected = self.root / 'expected.json'
        expected.write_text(self.manifest())
        self.file.write_text('old\n')
        prepare.SOURCE_LOCK.write_text(json.dumps({'mpvUpdate': {
            'baselineInputSHA256': base, 'patchedInputSHA256': prepare.digest(expected),
            'patch': patch_file.name, 'patchSHA256': prepare.digest(patch_file)}}))
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.dest = self.root / 'output'

    def manifest(self):
        row = {'path': self.rel, 'size': self.file.stat().st_size, 'sha256': prepare.digest(self.file)}
        return json.dumps({'files': [row]}, indent=2) + '\n'

    def test_output_inside_checkout(self):
        prepare.prepare(self.src, self.dest)
        self.assertEqual((self.dest / self.rel).read_text(), 'new\n')
        self.assertEqual(self.file.read_text(), 'old\n')
        with self.assertRaises(FileExistsError):
            prepare.prepare(self.src, self.dest)

    def test_normal_core_patch_order_and_identity(self):
        extra = self.root / 'phase30.patch'
        extra.write_text('--- a/audio.c\n+++ b/audio.c\n@@ -1 +1 @@\n-new\n+final\n')
        lock = json.loads(prepare.SOURCE_LOCK.read_text())
        update = lock['mpvUpdate']
        update['additionalPatches'] = [{'patch': extra.name, 'patchSHA256': prepare.digest(extra)}]
        self.file.write_text('final\n')
        expected = self.root / 'final.json'
        expected.write_text(self.manifest())
        self.file.write_text('old\n')
        update['patchedInputSHA256'] = prepare.digest(expected)
        prepare.SOURCE_LOCK.write_text(json.dumps(lock))
        prepare.prepare(self.src, self.dest)
        self.assertEqual((self.dest / self.rel).read_text(), 'final\n')
        extra.write_text('tampered')
        other = self.root / 'other'
        with self.assertRaisesRegex(ValueError, '补丁与来源锁不匹配'):
            prepare.prepare(self.src, other)
        self.assertFalse(other.exists())

    def test_nested_output(self):
        """未创建的多级父目录也可承载独立的派生输入。"""
        target = self.root / 'nested' / 'outputs' / 'copy'
        prepare.prepare(self.src, target)
        self.assertEqual((target / self.rel).read_text(), 'new\n')

    def test_modified_input(self):
        self.file.write_text('other\n')
        with self.assertRaisesRegex(ValueError, '封存输入不匹配'):
            prepare.prepare(self.src, self.dest)
        self.assertFalse(self.dest.exists())

class ArchivedInputTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('VIDALL_PHASE30_INPUT'), '未提供 Phase30 A 归档输入')
    def test_archived_input_matches_repository_lock(self):
        """用封存输入和仓内来源锁独立派生清单。"""
        source = Path(os.environ['VIDALL_PHASE30_INPUT'])
        lock = json.loads(prepare.SOURCE_LOCK.read_text())['mpvUpdate']
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'output'
            prepare.prepare(source, output)
            self.assertEqual(prepare.digest(output / 'package.json'), lock['patchedInputSHA256'])

if __name__ == '__main__':
    unittest.main()
