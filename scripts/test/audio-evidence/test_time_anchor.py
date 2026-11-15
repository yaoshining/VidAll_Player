import unittest, importlib.util, json
from unittest.mock import patch
from pathlib import Path
s=importlib.util.spec_from_file_location('anchor',Path(__file__).with_name('time_anchor.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class AnchorTest(unittest.TestCase):
 def test_visual(self):
  for n in [0,1,2048,4095]:
   bits=[1,1,0]+[(n>>i)&1 for i in range(11,-1,-1)];bits.append(sum(bits)%2)
   self.assertEqual(m.decode_code([255*b for b in bits]),n)
   bits[7]^=1;self.assertIsNone(m.decode_code([255*b for b in bits]))
  self.assertIsNone(m.decode_code([127]*16));self.assertIsNone(m.decode_code([0]*16))
 def test_timestamp(self):
  samples=[dict(framePos=i*48000,timestamp=(100+i)*1e9,beforeMonoNs=(100+i)*1e9,afterMonoNs=(100+i)*1e9+1e6,writtenFrames=(i+1)*48000) for i in range(1,13)]
  self.assertAlmostEqual(m.audio_origin(samples),100)
  for field,value in [('timestamp',1.7e18),('framePos',0),('writtenFrames',0)]:
   bad=[dict(x) for x in samples];bad[5][field]=value
   with self.assertRaises(ValueError):m.audio_origin(bad)
  bad=[dict(x) for x in samples];bad[5]['timestamp']+=100e6
  with self.assertRaises(ValueError):m.audio_origin(bad)
 def test_audio_pts(self):
  with patch.object(m,'run',return_value=b'{"frames":[]}'):
   with self.assertRaises(ValueError):m.first_audio_pts(Path('capture.mp4'))
  with patch.object(m,'run',return_value=b'{"frames":[{"best_effort_timestamp_time":"0.128"}]}'):
   self.assertEqual(m.first_audio_pts(Path('capture.mp4')), .128)
 def test_calibration(self):
  for value in [float("nan"), float("inf"), -.01]:
   self.assertEqual(m.classify(.150,.149,value), "inconclusive")
  self.assertEqual(m.classify(.150,.149,.01), 'capture-delay-supported')
  self.assertEqual(m.classify(.150,.010,.01), 'output-offset-remains')
  self.assertEqual(m.classify(.150,.149,.100), 'inconclusive')
  self.assertEqual(m.classify(.150,.149,.055), 'capture-delay-supported')
  self.assertEqual(m.classify(.150,.090,.055), 'inconclusive')
if __name__=='__main__':unittest.main()
