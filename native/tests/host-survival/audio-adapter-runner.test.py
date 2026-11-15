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

if __name__ == '__main__':
    unittest.main()
