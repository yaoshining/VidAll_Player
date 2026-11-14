"""独立原始时间轴：固定错位、回调迟到、断裂与边界不能被隐藏。"""
import unittest,struct,subprocess,tempfile,math
from pathlib import Path
import raw_capture as m
class RawTests(unittest.TestCase):
 def test_collector(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'test'
   root=Path(__file__).resolve().parents[3]
   subprocess.run(['c++','-std=c++17','-I'+str(root/'fixtures/normal-core-consumer/raw-capture'),str(Path(__file__).with_name('raw-capture.test.cpp')),'-o',str(exe)],check=True,timeout=30)
   subprocess.run([str(exe)],check=True,timeout=5)
 def test_records(self):
  a=struct.pack('<IIqq',2,8,100,900)+b'\0'*8
  self.assertEqual(m.decode(b'VRAWC001'+a)[0]['timestamp'],100)
  for data in (b'',b'VRAWC001'+a[:-1],b'VRAWC001'+a+a):
   with self.assertRaises(ValueError):m.decode(data)
 def test_continuity(self):
  a=[dict(timestamp=1000000000,payload=b'\0'*1920),dict(timestamp=1010000000,payload=b'\0'*1920)]
  self.assertLess(m.audio_continuity(a),.00001)
  a[1]['timestamp']+=10000000
  with self.assertRaises(ValueError):m.audio_continuity(a)
 def test_forensic_preserves_anomalies(self):
  a=struct.pack('<IIqq',2,8,100,900)+b'\0'*8
  rows=m.decode(b'VRAWC001'+a+a,strict=False)
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]['timestamp'],rows[1]['timestamp'])
 def test_raw_pulse_uses_media_timestamp(self):
  tone=b''.join(struct.pack('<hh',int(10000*math.sin(2*math.pi*2200*i/48000)),int(10000*math.sin(2*math.pi*2200*i/48000))) for i in range(960))
  rows=[dict(timestamp=1000000000,arrival=5000000000,payload=tone),dict(timestamp=1020000000,arrival=6000000000,payload=b'\0'*3840),dict(timestamp=1040000000,arrival=7000000000,payload=tone)]
  self.assertEqual(m.audio_edges(rows,2200),[1,1.04])
 def test_timestamp_not_arrival(self):
  # 输入脉冲按媒体时钟比较，200ms回调迟到不能被当成声音输出延迟。
  self.assertTrue(m.compare([1,3,5],[1.02,3.02,5.02])['signalPassed'])
  self.assertFalse(m.compare([1,3,5],[1.14,3.14,5.14])['signalPassed'])
  self.assertFalse(m.compare([1,3,5],[1,5])['signalPassed'])
if __name__=='__main__':unittest.main()
