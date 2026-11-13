import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
spec=importlib.util.spec_from_file_location('prepare_audio',Path(__file__).with_name('prepare.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=Path(__file__).resolve().parents[3]
class PrepareTest(unittest.TestCase):
 def test_generated_capture_stage_display_is_bounded(self):
  for kind in ['recovery-fence','recovery-terminal']:
   source=(ROOT/'fixtures/normal-core-consumer'/kind/'Index.ets').read_text()
   generated=m.with_capture(source)
   self.assertIn('Text(this.captureTrace)',generated)
   start=generated.index('  private record(')
   end=generated.index('  aboutToAppear()',start)
   record=generated[start:end]
   program="""
const assert=require('node:assert/strict');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const text='class Probe { root=""; captureTrace=""; captureTraceLines: string[]=[]; '+JSON.parse(process.argv[1])+' } exports.Probe=Probe;';
const output=ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const box={};new Function('exports','console',output)(box,{info(){}});
const p=new box.Probe();p.record('capture-stage','init');assert.equal(p.captureTrace,'capture-stage: init');
p.record('playback-progress','ignored');assert.equal(p.captureTraceLines.length,1);
for(let i=0;i<20;i++)p.record('capture-stage','stage-'+i+'\\n'+'x'.repeat(300));
const lines=p.captureTrace.split('\\n');assert.equal(lines.length,12);assert(lines.every(x=>x.length<=160));
assert(lines[0].includes('stage-8'));assert(lines[11].includes('stage-19'));
"""
   subprocess.run(['node','-e',program,json.dumps(record)],cwd=ROOT,check=True)
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
  for marker in ['private maybeStart(): void {','private async run(): Promise<void> {','aboutToDisappear(): void {','Stack({ alignContent: Alignment.TopStart }) {',"private record(event: string, value: string = ''): void {",'Text(this.status)']:
   with self.assertRaises(ValueError):m.with_capture(source.replace(marker,'changed'))
 def test_double_wrap_rejected(self):
  source=(ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text()
  with self.assertRaises(ValueError):m.with_capture(m.with_capture(source))
if __name__=='__main__':unittest.main()
