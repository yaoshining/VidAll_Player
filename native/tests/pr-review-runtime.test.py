"""合并前真实 Monitor 退出、正常 deadline 和同步终局事件回归。"""
import os,subprocess,tempfile,threading,time,unittest
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
  # 在父进程的同一个单调时钟上测量，Darwin 的 C++ 与 Python 时钟原点可能不同。
  root=self.base/'deadline'
  root.mkdir()
  with subprocess.Popen([str(self.bin),'deadline',str(root)],stderr=subprocess.PIPE,text=True) as proc:
   observed=[]
   def read_marker():
    for line in proc.stderr:
     if line.startswith('TERMINAL_AT '): observed.append(time.monotonic())
   reader=threading.Thread(target=read_marker)
   reader.start()
   try:
    rc=proc.wait(timeout=10)
    exited=time.monotonic()
   finally:
    if proc.poll() is None: proc.kill()
    reader.join()
   self.assertEqual(rc,86)
   self.assertEqual(len(observed),1)
   self.assertGreaterEqual(exited-observed[0],0.95)
   self.assertLess(exited-observed[0],2.5)
 def test_synchronous_terminal_listener(self):
  env=dict(os.environ,TYPESCRIPT_PATH=str(ROOT/'scripts/test/normal-core/node_modules/typescript'))
  r=subprocess.run(['node','native/tests/normal-runtime.test.cjs','constructor-terminal-replay'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
