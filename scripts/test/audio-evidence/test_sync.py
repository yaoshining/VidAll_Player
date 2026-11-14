#!/usr/bin/env python3
"""同步工具正常、缺失、错位及漂移负例；合成测试不能冒充实机。"""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('av_sync',Path(__file__).with_name('av_sync.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SyncTests(unittest.TestCase):
 def test_normal(self):
  r=m.compare([1,3,5,7],[1.02,3.02,5.02,7.02]);self.assertTrue(r['signalPassed']);self.assertFalse(r['deviceAccepted'])
 def test_missing_audio(self):self.assertFalse(m.compare([1,3,5,7],[])['signalPassed'])
 def test_missing_frame(self):self.assertFalse(m.compare([1,5,7],[1,3,5,7])['signalPassed'])
 def test_offset(self):self.assertFalse(m.compare([1,3,5,7],[1.2,3.2,5.2,7.2])['signalPassed'])
 def test_drift(self):self.assertFalse(m.compare([1,3,5,7],[1,3.01,5.06,7.07])['signalPassed'])
 def test_too_short(self):self.assertFalse(m.compare([1],[1])['signalPassed'])
 def test_non_finite(self):
  with self.assertRaises(ValueError):m.compare([1,float('nan'),5],[1,3,5])
 def test_duplicate(self):
  with self.assertRaises(ValueError):m.compare([1,1,5],[1,3,5])
 def test_edges(self):self.assertEqual(m.rising_edges([0,.01,.02,.03,.04],[0,1,1,0,1]),[.01,.04])
if __name__=='__main__':unittest.main()
