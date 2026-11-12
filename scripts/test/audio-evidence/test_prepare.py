import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('prepare_audio',Path(__file__).with_name('prepare.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=Path(__file__).resolve().parents[3]
class PrepareTest(unittest.TestCase):
 def test_both_real_probes_preserve_acceptance_guards(self):
  for kind in ['recovery-fence','recovery-terminal']:
   source=(ROOT/'fixtures/normal-core-consumer'/kind/'Index.ets').read_text()
   generated=m.with_capture(source)
   self.assertEqual(source.count('XComponent({'),generated.count('XComponent({'))
   self.assertIn('if (!this.audioRequested) return;',generated)
   self.assertIn('await this.runUnrecorded();',generated)
   self.assertIn('await this.capture.finish();',generated)
   if kind=='recovery-fence':self.assertIn('await runFenceProbe(port)',generated)
   else:self.assertIn('initialMode(this.profile, generation)',generated)
 def test_source_drift_rejected(self):
  source=(ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text()
  for marker in ['private maybeStart(): void {','private async run(): Promise<void> {','aboutToDisappear(): void {','Stack({ alignContent: Alignment.TopStart }) {']:
   with self.assertRaises(ValueError):m.with_capture(source.replace(marker,'changed'))
 def test_double_wrap_rejected(self):
  source=(ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text()
  with self.assertRaises(ValueError):m.with_capture(m.with_capture(source))
if __name__=='__main__':unittest.main()
