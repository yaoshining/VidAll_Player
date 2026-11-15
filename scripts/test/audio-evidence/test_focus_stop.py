"""焦点暂停交接按实际10ms覆盖率，不以200ms频谱块放大短尾。"""
import math,unittest
from array import array
from focus_stop import measure_focus_stop
RATE=16000

def pcm(tail=0.02,late=False,alarm=True):
 return array('h',[round(4000*((math.sin(2*math.pi*440*i/RATE) if i/RATE<tail or late and 1<i/RATE<1.04 else 0)+(math.sin(2*math.pi*1320*i/RATE) if alarm and i/RATE>.03 else 0))) for i in range(2*RATE)])

class FocusStopTest(unittest.TestCase):
 def test_short_initial_tail_uses_actual_duration(self):
  r=measure_focus_stop(pcm(),RATE,1,0,2,440,1320)
  self.assertTrue(r['passed']);self.assertAlmostEqual(r['oldAudioSeconds'],.02,places=6)
 def test_persistent_audio_fails(self):
  self.assertFalse(measure_focus_stop(pcm(.2),RATE,1,0,2,440,1320)['passed'])
 def test_late_audio_reappearance_fails_even_with_high_coverage(self):
  self.assertFalse(measure_focus_stop(pcm(late=True),RATE,1,0,2,440,1320)['passed'])
 def test_missing_alarm_fails(self):
  self.assertFalse(measure_focus_stop(pcm(alarm=False),RATE,1,0,2,440,1320)['passed'])
 def test_short_window_rejected(self):
  with self.assertRaises(ValueError):measure_focus_stop(pcm(),RATE,1,0,.5,440,1320)
if __name__=='__main__':unittest.main()
