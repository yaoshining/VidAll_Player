"""独立派生输入时不能静默跳过补丁，失败不能留下半成品。"""
import importlib.util
import json
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
        patch = self.root / 'fix.patch'
        patch.write_text('--- a/audio.c\n+++ b/audio.c\n@@ -1 +1 @@\n-old\n+new\n')
        prepare.ROOT = self.root
        prepare.SOURCE_LOCK = self.root / 'lock.json'
        base = prepare.digest(self.index)
        self.file.write_text('new\n')
        expected = self.root / 'expected.json'
        expected.write_text(self.manifest())
        self.file.write_text('old\n')
        prepare.SOURCE_LOCK.write_text(json.dumps({'mpvUpdate': {
            'baselineInputSHA256': base, 'patchedInputSHA256': prepare.digest(expected),
            'patch': patch.name, 'patchSHA256': prepare.digest(patch)}}))
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

    def test_modified_input(self):
        self.file.write_text('other\n')
        with self.assertRaisesRegex(ValueError, '封存输入不匹配'):
            prepare.prepare(self.src, self.dest)
        self.assertFalse(self.dest.exists())

if __name__ == '__main__':
    unittest.main()
