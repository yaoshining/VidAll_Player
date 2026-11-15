"""确保跨平台失败的场景名及原始诊断进入CI公开日志。"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('adapter_runner', Path(__file__).with_name('run-audio-adapter.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class RunnerTests(unittest.TestCase):
    def check_result(self, fail):
        def execute(cmd, **kwargs):
            bad = fail and cmd[-1] == 'clock'
            return subprocess.CompletedProcess(cmd, 1 if bad else 0, '', 'fixture clock assertion' if bad else '')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'results.json'
            log = io.StringIO()
            with patch('sys.argv', ['run-audio-adapter.py', '--out', str(out)]), patch.object(runner.subprocess, 'run', side_effect=execute), contextlib.redirect_stdout(log):
                if fail:
                    with self.assertRaises(SystemExit) as result:
                        runner.main()
                    self.assertEqual(result.exception.code, 1)
                else:
                    runner.main()
            rows = json.loads(out.read_text())['cases']
            self.assertEqual(len(rows), len(runner.CASES))
            if fail:
                self.assertIn('clock: FAIL', log.getvalue())
                self.assertIn('fixture clock assertion', log.getvalue())
            else:
                self.assertNotIn('FAIL', log.getvalue())

    def test_failure_keeps_diagnostic_and_nonzero(self):
        self.check_result(True)

    def test_success_preserves_all_cases(self):
        self.check_result(False)

    def test_timeout_keeps_output_and_collects_remaining_cases(self):
        for captured in [b'before timeout', 'before timeout', None]:
            with self.subTest(captured=captured), tempfile.TemporaryDirectory() as d:
                out = Path(d) / 'results.json'
                log = io.StringIO()
                executed = []
                def execute(cmd, **kwargs):
                    if cmd[-1] in runner.CASES:
                        executed.append(cmd[-1])
                    if cmd[-1] == 'focus':
                        raise subprocess.TimeoutExpired(cmd, 15, output=captured, stderr=captured)
                    return subprocess.CompletedProcess(cmd, 0, 'normal output', '')
                with patch('sys.argv', ['run-audio-adapter.py', '--out', str(out)]), patch.object(runner.subprocess, 'run', side_effect=execute), contextlib.redirect_stdout(log):
                    with self.assertRaises(SystemExit) as result:
                        runner.main()
                self.assertEqual(result.exception.code, 1)
                self.assertEqual(executed, runner.CASES)
                rows = json.loads(out.read_text())['cases']
                self.assertEqual([r['case'] for r in rows], runner.CASES)
                timeout = rows[1]
                self.assertEqual(timeout['exit'], 124)
                self.assertTrue(timeout['timedOut'])
                self.assertIn('TIMEOUT', timeout['output'])
                self.assertIn('focus: FAIL', log.getvalue())
                if captured is not None:
                    self.assertEqual(timeout['output'].count('before timeout'), 2)
                    self.assertIn('before timeout', log.getvalue())
                self.assertEqual(rows[0]['exit'], 0)
                self.assertEqual(rows[-1]['exit'], 0)

if __name__ == '__main__':
    unittest.main()
