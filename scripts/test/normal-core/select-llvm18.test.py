#!/usr/bin/env python3
"""真实子进程验证选择器；临时可执行文件只模拟各工具的版本协议。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('select-llvm18.py')
TOOLS = ('clang', 'clang++', 'llvm-nm')


class LLVMSelectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vidall-llvm-selection-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = self.root / 'llvm bin'
        self.tools.mkdir()
        self.github_path = self.root / 'github-path'
        self.github_path.write_text('/already-selected\n')
        for name in TOOLS:
            self.tool(name)

    def tool(self, name, major=18, exit_code=0, executable=True, text=None):
        if text is None:
            text = (f'Ubuntu clang version {major}.1.8\nTarget: x86_64-pc-linux-gnu'
                    if name != 'llvm-nm' else f'llvm-nm, compatible with GNU nm\nUbuntu LLVM version {major}.1.8')
        path = self.tools / name
        path.write_text('#!/bin/sh\n[ "$1" = "--version" ] || exit 9\ncat <<\'VERSION\'\n'
                        + text + '\nVERSION\nexit ' + str(exit_code) + '\n')
        path.chmod(0o755 if executable else 0o644)

    def run_selector(self, directory=None, path_env=True):
        env = os.environ.copy()
        env.pop('GITHUB_PATH', None)
        if path_env:
            env['GITHUB_PATH'] = str(self.github_path)
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--tool-dir', str(directory or self.tools)],
                              env=env, text=True, capture_output=True, timeout=20)

    def rejected_without_append(self):
        before = self.github_path.read_bytes()
        result = self.run_selector()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.github_path.read_bytes(), before)
        self.assertNotIn('"selected": true', result.stdout)
        return result

    def test_select_complete_llvm18_and_preserve_existing_path(self):
        result = self.run_selector()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['major'], 18)
        self.assertTrue(report['selected'])
        self.assertEqual(report['directory'], str(self.tools.resolve()))
        self.assertEqual({row['tool'] for row in report['tools']}, set(TOOLS))
        for row in report['tools']:
            self.assertEqual(row['realPath'], str((self.tools / row['tool']).resolve()))
            self.assertIn('18.1.8', row['version'])
        self.assertEqual(self.github_path.read_text(), '/already-selected\n' + str(self.tools.resolve()) + '\n')

    def test_each_missing_tool_rejects_without_partial_path_write(self):
        for name in TOOLS:
            with self.subTest(tool=name):
                (self.tools / name).unlink()
                self.rejected_without_append()
                self.tool(name)

    def test_each_wrong_major_rejects(self):
        for name in TOOLS:
            for major in (17, 19, 180):
                with self.subTest(tool=name, major=major):
                    self.tool(name, major=major)
                    self.rejected_without_append()
            self.tool(name)

    def test_nonzero_version_result_rejects_even_when_text_matches(self):
        for name in TOOLS:
            with self.subTest(tool=name):
                self.tool(name, exit_code=7)
                self.rejected_without_append()
                self.tool(name)

    def test_non_executable_rejects(self):
        self.tool('clang++', executable=False)
        self.rejected_without_append()

    def test_directory_in_place_of_tool_rejects(self):
        (self.tools / 'llvm-nm').unlink()
        (self.tools / 'llvm-nm').mkdir()
        self.rejected_without_append()

    def test_unrelated_or_ambiguous_version_text_rejects(self):
        for text in ('vendor tool 18.1.8', 'clang version 18.1.8\nclang version 17.0.0', 'clang version 180.1.8'):
            with self.subTest(text=text):
                self.tool('clang', text=text)
                self.rejected_without_append()

    def test_real_path_follows_symlink_and_versions_can_be_upstream(self):
        self.tool('clang', text='clang version 18.1.8')
        target = self.tools / 'clang-real'
        (self.tools / 'clang').rename(target)
        (self.tools / 'clang').symlink_to(target.name)
        result = self.run_selector()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['tools'][0]['realPath'], str(target.resolve()))

    def test_missing_path_environment_rejects(self):
        result = self.run_selector(path_env=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.github_path.read_text(), '/already-selected\n')

    def test_newline_directory_cannot_inject_path_entries(self):
        injected = self.root / 'llvm\nother'
        self.tools.rename(injected)
        result = self.run_selector(directory=injected)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.github_path.read_text(), '/already-selected\n')

    def test_fixed_default_directory_ignores_path_lookup(self):
        # 默认路径契约独立核对，不触碰执行主机的 /usr/lib。
        source = SCRIPT.read_text()
        self.assertIn("default=Path('/usr/lib/llvm-18/bin')", source)
        self.assertNotIn('shutil.which', source)


if __name__ == '__main__':
    unittest.main()
