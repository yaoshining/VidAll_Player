"""源码缓存缺少锁定提交时安全刷新，下载失败必须保留旧树。"""
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).parents[1]/'scripts/build-libsmbclient-controlled.sh').read_text()
FUNCTIONS = SOURCE.split('# ---------------- 源码检出 ----------------')[1].split('# ---------------- 依赖链构建 ----------------')[0]

class SourceCacheTest(unittest.TestCase):
    def probe(self, cached, success, present=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root/'source'
            if cached:
                (target/'.git').mkdir(parents=True)
                (target/'old').write_text('keep')
            shell = '''set -euo pipefail
''' + FUNCTIONS + '''
git() { return "$COMMIT_PRESENT"; }
python3() {
  while [ "$1" != --destination ]; do shift; done
  shift
  test ! -e "$1" || return 90
  mkdir -p "$1/.git"
  echo new > "$1/new"
  return "$DOWNLOAD_RESULT"
}
ensure_samba_source "$TARGET"
'''
            import os
            result = subprocess.run(['bash', '-c', shell], env={**os.environ,
                'TARGET':str(target), 'SMB_SCRIPT_DIR':str(root), 'SAMBA_COMMIT':'a'*40,
                'COMMIT_PRESENT':'0' if present else '1', 'DOWNLOAD_RESULT':'0' if success else '1'}, capture_output=True,text=True)
            if present:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue((target/'old').exists())
                self.assertFalse((target/'new').exists())
            elif success:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue((target/'new').exists())
                self.assertFalse((target/'old').exists())
            else:
                self.assertNotEqual(result.returncode,0)
                self.assertTrue((target/'old').exists())
            self.assertEqual(list(root.iterdir()),[target])

    def test_empty_cache(self): self.probe(False,True)
    def test_stale_cache_replaced(self): self.probe(True,True)
    def test_download_failure_preserves_cache(self): self.probe(True,False)
    def test_valid_cache_reused(self): self.probe(True,False,True)
    def test_both_callers_use_same_guard(self):
        self.assertIn('ensure_samba_source "$SAMBA_DIR"',SOURCE)
        self.assertIn('ensure_samba_source "$SAMBA_HOST_DIR"',SOURCE)

if __name__ == '__main__': unittest.main()
