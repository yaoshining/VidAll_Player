"""编译并执行真实有界枚举实现的故障替身测试，不计设备能力。"""
import subprocess,tempfile,unittest
from pathlib import Path
class EnumerationTest(unittest.TestCase):
 def test_driver_enumeration_boundaries(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'probe-test'
   subprocess.run(['c++','-std=c++17',str(Path(__file__).with_name('presentation-enumeration.test.cpp')),'-o',str(exe)],check=True,timeout=30)
   subprocess.run([str(exe)],check=True,timeout=5)
if __name__=='__main__':unittest.main()
