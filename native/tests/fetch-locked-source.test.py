"""锁定源码获取：只取指定提交，网络停滞必须有界失败。"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('fetch', Path(__file__).parents[1] / 'scripts/fetch-locked-source.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

class FetchTest(unittest.TestCase):
    def test_locked_shallow_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'source'; source.mkdir()
            def git(*args):
                return subprocess.check_output(['git','-C',str(source),*args],text=True).strip()
            git('init','-q')
            (source/'file').write_text('locked')
            git('add','file')
            git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','locked')
            commit = git('rev-parse','HEAD')
            (source/'file').write_text('newer')
            git('add','file')
            git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','newer')
            dest = root/'dest'
            fetch.fetch(source.as_uri(), commit, dest, timeout=10, attempts=1)
            self.assertEqual((dest/'file').read_text(),'locked')
            self.assertTrue((dest/'.git/shallow').is_file())

    def test_timeout(self):
        start=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            fetch.run([sys.executable,'-c','import time; time.sleep(60)'],timeout=.1)
        self.assertLess(time.monotonic()-start,3)

    def test_retry_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(fetch,'run') as run, patch.object(fetch.time,'sleep'):
            run.side_effect=lambda cmd, **kw: (_ for _ in ()).throw(subprocess.CalledProcessError(1,cmd)) if 'fetch' in cmd else ''
            with self.assertRaises(subprocess.CalledProcessError):
                fetch.fetch('https://example.invalid/source.git','a'*40,Path(temp)/'dest',timeout=1,attempts=3)
            calls=[c.args[0] for c in run.call_args_list if 'fetch' in c.args[0]]
            self.assertEqual(len(calls),3)
            self.assertTrue(all('--depth=1' in c and '--no-tags' in c for c in calls))

    def test_mismatched_commit_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(fetch,'run',return_value='b'*40):
            with self.assertRaises(ValueError):
                fetch.fetch('https://example.invalid/source.git','a'*40,Path(temp)/'dest',timeout=1,attempts=1)

    def test_floating_ref_rejected(self):
        with self.assertRaises(ValueError):
            fetch.fetch('https://example.invalid/source.git','main',Path('/unused'),timeout=1,attempts=1)

if __name__ == '__main__': unittest.main()
