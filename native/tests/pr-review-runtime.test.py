"""合并前真实 Monitor 退出、正常 deadline 和同步终局事件回归。"""
import os,re,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name);cls.bin=cls.base/'monitor'
  subprocess.run(['clang++','-std=c++17','-pthread','-DVIDALL_MPV_AVAILABLE=1','-I'+str(ROOT/'release/inputs/004-normal-core/include'),str(ROOT/'native/tests/normal-monitor.test.cpp'),'-o',str(cls.bin)],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def run_mode(self,mode):
  root=self.base/mode;root.mkdir();start=time.monotonic();r=subprocess.run([str(self.bin),mode,str(root)],capture_output=True,text=True,timeout=10);return r,time.monotonic()-start
 def test_enable_failure_returns_from_real_monitor(self):
  r,_=self.run_mode('enable-failed');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('MONITOR_RETURNED',r.stdout)
 def test_normal_remains_ready(self):
  r,_=self.run_mode('normal');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('READY',r.stdout)
 def test_normal_terminal_deadline(self):
  r,_=self.run_mode('deadline');self.assertEqual(r.returncode,86,r.stderr);match=re.search(r'TERMINAL_AT (\d+)',r.stderr);self.assertIsNotNone(match);elapsed=time.monotonic()-int(match[1])/1000;self.assertGreaterEqual(elapsed,0.95);self.assertLess(elapsed,2.5)
 def test_synchronous_terminal_listener(self):
  env=dict(os.environ,TYPESCRIPT_PATH=str(ROOT/'scripts/test/normal-core/node_modules/typescript'))
  r=subprocess.run(['node','native/tests/normal-runtime.test.cjs','constructor-terminal-replay'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
