"""已停止Release挂起验收变体保留真实导航与拒绝失效注入。"""
import unittest
from pathlib import Path
import prepare,prepare_anchor
import prepare_release_hold as m
ROOT=Path(__file__).resolve().parents[3]
class Test(unittest.TestCase):
 def test_transform(self):
  src=prepare_anchor.transform(prepare.with_capture((ROOT/'fixtures/normal-core-consumer/recovery-terminal/Index.ets').read_text()),'global')
  out=m.transform(src)
  for s in ['release-probe.mp4','release-probe-request',"scope: 'stopped-release-hold'",'release-probe-rejected','await this.waitForRecoveryNavigation()',"calibrate('after')",'await first.play()','RECOVERY_NOT_READY']:self.assertIn(s,out)
  self.assertNotIn('global-probe.mp4',out)
  self.assertLess(out.index('release-probe-request'),out.index('GLOBAL_PROBE_NOT_FIRED'))
  with self.assertRaises(ValueError):m.transform(out)
 def test_drift(self):
  with self.assertRaises(ValueError):m.transform('struct Index {}')
if __name__=='__main__':unittest.main()
