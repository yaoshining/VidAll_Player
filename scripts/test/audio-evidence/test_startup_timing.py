"""独立起音定位的正常、边界及失败回归，不改完整窗口门槛。"""
import unittest,math,tempfile,wave
from array import array
from pathlib import Path
from startup_timing import onset, frame_origin, decompose
class Test(unittest.TestCase):
 def samples(self,delay=0,hz=880,amp=.1,channels=1):
  out=[]
  for i in range(48000):
   v=round(32767*amp*math.sin(2*math.pi*hz*i/48000)) if i>=round(delay*48000) else 0
   out.extend([v] if channels==1 else [v,-v])
  return out
 def test_delays_and_stereo(self):
  for delay in [0,.03,.12,.2,.33,.4]:
   for channels in [1,2]:
    r=onset(self.samples(delay,channels=channels),48000,channels,0,1,880,440)
    self.assertLessEqual(abs(r['firstOnsetSeconds']-delay),.010001)
 def test_wrong_tone_and_silence(self):
  for samples in [self.samples(hz=440),self.samples(amp=0),self.samples(amp=.0001)]:
   self.assertIsNone(onset(samples,48000,1,0,1,880,440)['firstOnsetSeconds'])
 def test_bounds(self):
  for end in [float('nan'),2,0]:
   with self.assertRaises(ValueError):onset(self.samples(),48000,1,0,end,880,440)
  with self.assertRaises(ValueError):onset(self.samples(),48000,1,0,1,880,880)
 def test_decomposition_same_clock(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'tone.wav'
   with wave.open(str(p),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(array('h',self.samples(.3)).tobytes())
   log='100 P17 firstFrame 1\n100.1 first video frame after restart shown\n'
   for i in range(1,5):
    log+=f'AUDIO_START_TRACE token=257 mono=10200000000 mpv=200000000 pos={i*4800} platform={10300000000+i*100000000} valid=1 cb=180000000 ret=180000000 pcm=180000000\n'
   r=decompose(p,dict(calibrationValid=True,monotonicMinusWallSeconds=-90,uncertaintyMs=40),dict(eventWindows=[dict(start=0)],alignment=dict(wallToAudioPtsSeconds=-100),signalPassed=False),log)
   self.assertAlmostEqual(r['firstFrameToOnsetMs'],300,places=5)
   self.assertAlmostEqual(r['videoReadyToPlatformFirstFrameMs'],200,places=5)
   self.assertAlmostEqual(r['platformFirstFrameToRecordedOnsetMs'],0,places=5)
   self.assertFalse(r['originalGatePassed']);self.assertFalse(r['physicalAccepted'])
 def test_missing_calibration(self):
  with self.assertRaises(ValueError):decompose(None,dict(calibrationValid=False),{},"")
 def test_platform_origin(self):
  rows=[dict(position=i*4800,timestampNs=1000000000+i*100000000) for i in range(1,5)]
  self.assertAlmostEqual(frame_origin(rows,48000)['originSeconds'],1)
  for bad in [[],rows[:1],rows+[rows[-1]],rows+[dict(position=24000,timestampNs=2000000000)]]:
   with self.assertRaises(ValueError):frame_origin(bad,48000)
if __name__=='__main__':unittest.main()
