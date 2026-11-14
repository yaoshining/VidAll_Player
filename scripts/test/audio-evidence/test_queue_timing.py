import unittest
from queue_timing import summarize
class QueueTimingTest(unittest.TestCase):
 def test_wait_and_duplicate_sampling(self):
  log='\n'.join([
   'AUDIO_QUEUE_TRACE token=257 i=0 rate=48000 enter=1000000000 leave=1000100000 samples=960 written=0 queued=0 pos=0 stamp=0 end=1020000000 nonzero=1',
   'AUDIO_QUEUE_TRACE token=257 i=1 rate=48000 enter=1020000000 leave=1020100000 samples=960 written=960 queued=0 pos=0 stamp=1000000000 end=1040000000 nonzero=1',
  ]+['AUDIO_START_TRACE token=257 mono=%d mpv=%d pos=%d platform=%d valid=1 cb=1000000000 ret=1000100000 pcm=1000100000'%(t,t,p,t) for t,p in [(1100000000,960),(1100000000,960),(1120000000,1920),(1140000000,2880)]])
  r=summarize(log)[0]
  self.assertAlmostEqual(r['callbackPeriodMs'],20)
  self.assertAlmostEqual(r['pcmToPlatformOriginMs'],79.9)
  self.assertAlmostEqual(r['zeroPositionExtrapolationMaxMs'],20)
  self.assertFalse(r['physicalAccepted'])
 def test_missing(self):
  with self.assertRaises(ValueError):summarize('no data')
 def test_partial(self):
  with self.assertRaises(ValueError):summarize('AUDIO_QUEUE_TRACE token=257 i=0 rate=0')
if __name__=='__main__':unittest.main()
