#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).with_name('prepare_sync.py');spec=importlib.util.spec_from_file_location('prepare_sync',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=Path(__file__).resolve().parents[3]
class PrepareSyncTests(unittest.TestCase):
 def test_interventions_preserved(self):
  src=(ROOT/'fixtures/normal-core-consumer/audio-evidence/Index.ets').read_text();out=m.transform(src)
  for text in ['this.badMedia()', 'this.focusFlow(first)', 'await first.pause()', 'await first.play()', 'first.release()', 'this.open(2)', 'this.acceptManualResume()', 'this.capture.assertRecording()']:self.assertIn(text,out)
  self.assertIn('await this.delay(90000)',out);self.assertIn('const target = 120000',out);self.assertIn('durationMs, true) - 180000',out);self.assertIn('await this.delay(10000)',out)
 def test_drift_rejected(self):
  with self.assertRaises(ValueError):m.transform('struct Index {}')
 def test_no_repeated_application(self):
  src=(ROOT/'fixtures/normal-core-consumer/audio-evidence/Index.ets').read_text()
  with self.assertRaises(ValueError):m.transform(m.transform(src))
if __name__=='__main__':unittest.main()
