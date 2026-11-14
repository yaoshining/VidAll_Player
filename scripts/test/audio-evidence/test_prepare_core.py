"""核心验收壳的交互门槛与产物边界回归。"""
import tempfile, unittest
from pathlib import Path
from prepare_core import prepare
class CorePageTest(unittest.TestCase):
 def test_recording_keeps_manual_controls_outside_hidden_console(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'entry/libs').mkdir(parents=True);(p/'entry/src/main/ets/pages').mkdir(parents=True)
   har=p/'entry/libs/current.har';har.write_bytes(b'original-ci-artifact')
   prepare(p)
   self.assertEqual(har.read_bytes(),b'original-ci-artifact')
   s=(p/'entry/src/main/ets/pages/Index.ets').read_text();ui=s[s.index('  build() {'):]
   self.assertIn('if (!this.captureBusy)',ui)
   # 控制台关闭之后才画手动按钮；录制时按钮仍存在且不会被整块控制台遮住。
   close=ui.index("      }\n      if (this.awaitingManualResume)")
   self.assertGreater(ui.index("Button('返回视频列表')"),close)
   self.assertGreater(ui.index("Button('手动继续播放')"),close)
   self.assertIn("await this.waitForRecoveryNavigation();",s)
   self.assertIn("'/second_video.mp4'",s)
   self.assertIn("throw new Error('HARDWARE_PATH_MISSING')",s)
if __name__=='__main__':unittest.main()
