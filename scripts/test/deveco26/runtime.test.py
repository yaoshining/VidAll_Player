#!/usr/bin/env python3
"""真实CMake解释器检查runtime开关；不模拟目标编译器。"""
import os,subprocess,tempfile,unittest,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CMAKE=os.environ['DEVECO26_CMAKE']
class Runtime(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.out=Path(self.t.name)
 def run_case(self,on='ON',arch='arm64-v8a',stl='none',bad=False):
  runtime=ROOT/'release/inputs/004-normal-core/arm64-v8a/libc++_shared.so'
  if bad:runtime=self.out/'bad.so';runtime.write_bytes(b'wrong')
  script=self.out/'test.cmake';script.write_text(f'''set(VIDALL_FIXED_CXX_RUNTIME {on})\ninclude("{ROOT}/native/cmake/fixed-cxx-runtime.cmake")\nvidall_check_fixed_runtime("{runtime}" "{arch}" "{stl}")\n''')
  return subprocess.run([CMAKE,'-P',script],capture_output=True,text=True,timeout=15)
 def test_actual_selected_headers_use_ohos_namespace(self):
  sdk=Path(os.environ['DEVECO26_SDK'])
  cmake=(ROOT/'packages/vidall-player/src/main/cpp/CMakeLists.txt').read_text()
  suffix=re.search(r'target_include_directories\(vidall_player_native SYSTEM PRIVATE "\$\{OHOS_SDK_NATIVE\}(/[^"\n]+)"',cmake).group(1)
  r=subprocess.run([str(sdk/'llvm/bin/clang++'),'--target=aarch64-linux-ohos','--sysroot='+str(sdk/'sysroot'),'-nostdinc++','-isystem',str(sdk)+suffix,'-x','c++','-dM','-E','-'],input='#include <__config>\n',capture_output=True,text=True,timeout=15)
  self.assertEqual(r.returncode,0);self.assertIn('#define _LIBCPP_ABI_NAMESPACE __n1',r.stdout)
 def test_enabled_accepts_fixed(self):self.assertEqual(self.run_case().returncode,0)
 def test_wrong_arch(self):
  r=self.run_case(arch='x86_64');self.assertNotEqual(r.returncode,0);self.assertIn('ARM64',r.stderr)
 def test_wrong_stl(self):
  r=self.run_case(stl='c++_shared');self.assertNotEqual(r.returncode,0);self.assertIn('OHOS_STL=none',r.stderr)
 def test_wrong_runtime(self):
  r=self.run_case(bad=True);self.assertNotEqual(r.returncode,0);self.assertIn('SHA256',r.stderr)
 def test_default_off_preserves_path(self):self.assertEqual(self.run_case(on='OFF',arch='x86_64',stl='c++_shared',bad=True).returncode,0)
if __name__=='__main__':unittest.main()
