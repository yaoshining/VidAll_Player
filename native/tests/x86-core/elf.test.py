"""对真实 x86 核心及错误架构/依赖/导出变体检查，不冒充设备运行。"""
from pathlib import Path
import importlib.util
import sys
import unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
s=importlib.util.spec_from_file_location('audit',ROOT/'scripts/audit/x86-core-verify.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Elf(unittest.TestCase):
 def setUp(self):self.data=(ROOT/'release/inputs/018-x86-core/x86_64/libmpv.so').read_bytes()
 def test_real_core(self):
  info=m.inspect(self.data);self.assertIn('mpv_host_recovery_stop_audio',info['exports']);self.assertIn('OH_AudioRenderer_Start',info['imports']);m.validate_core(info)
 def test_wrong_architecture(self):
  bad=bytearray(self.data);bad[18:20]=(183).to_bytes(2,'little')
  with self.assertRaises(ValueError):m.inspect(bytes(bad))
 def test_no_probe_core(self):
  info=m.inspect(self.data);info['exports'].remove('mpv_host_loadfile_async')
  with self.assertRaises(ValueError):m.validate_core(info)
 def test_no_hardware_calls(self):
  info=m.inspect(self.data);info['imports'].add('av_ohcodec_release_buffer')
  with self.assertRaises(ValueError):m.validate_core(info)
 def test_unknown_needed(self):
  info=m.inspect(self.data);info['needed'].append('libunknown.so')
  with self.assertRaises(ValueError):m.validate_core(info)
if __name__=='__main__':unittest.main()
