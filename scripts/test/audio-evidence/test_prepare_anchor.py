import unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def module(name):
 s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Test(unittest.TestCase):
 def test_normal(self):
  m=module('prepare_anchor');src=module('prepare_sync').transform((ROOT/'fixtures/normal-core-consumer/audio-evidence/Index.ets').read_text());out=m.transform(src,'normal')
  for token in ['anchor-visual-row',"calibrate('before')","calibrate('after')",'anchor?.close()', 'await first.seekPercent', 'await first.release()','this.badMedia()']:self.assertIn(token,out)
  self.assertIn("String(index) + '-' + String(bit)",out)
  self.assertLess(out.index("calibrate('before')"),out.index('if (systemBaseline)'))
  with self.assertRaises(ValueError):m.transform(out,'normal')
 def test_fence(self):
  m=module('prepare_anchor');src=module('prepare').with_capture((ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text());out=m.transform(src,'fence')
  for token in ['await this.delay(10000); this.active();', 'release-heartbeat','this.runUnrecorded()',"calibrate('after')"]:
   self.assertIn(token,out)
  self.assertIn('confirmLateClose: (): Promise<void>',out)
 def test_drift(self):
  with self.assertRaises(ValueError):module('prepare_anchor').transform('struct Index {}','normal')
if __name__=='__main__':unittest.main()
