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
   self.assertIn("from './EvidenceChunks'", generated)
   self.assertIn(".id('audio-copy-capture')", generated)
   self.assertIn('this.chunks?.close()', generated)
   self.assertIn('this.captureBusy = true', generated)
   self.assertIn('this.captureBusy = false', generated)
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
   else:
    self.assertIn('initialMode(this.profile, generation)',generated)
    self.assertIn('const third = await this.open(3); await this.delay(2000);',generated)
    self.assertRegex(generated, r'Column\(\) \{\s+Row\(\)')
   self.assertIn('if (this.evidenceClosed || !this.root) return;',generated)
   self.assertIn('this.evidenceClosed = true;',generated)
 def test_failed_probe_can_export_until_page_disappears(self):
  program = """
const assert=require('node:assert/strict');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let calls=[];class EvidenceChunks{async begin(kind,busy){calls.push([kind,busy]);if(busy)throw Error('CAPTURE_BUSY');}}
const source='class Probe {root="/own";cancelled=true;evidenceClosed=false;captureBusy=false;evidenceStatus="";chunks;'+JSON.parse(process.argv[1])+'} exports.Probe=Probe;';
const box={};new Function('exports','EvidenceChunks',ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText)(box,EvidenceChunks);
(async()=>{let p=new box.Probe();await p.copyEvidence('events');assert.deepEqual(calls,[['events',false]]);p.captureBusy=true;await p.copyEvidence('capture');assert.match(p.evidenceStatus,/CAPTURE_BUSY/);p.evidenceClosed=true;await p.copyEvidence('events');assert.equal(calls.length,2);})().catch(e=>{console.error(e);process.exitCode=1;});
"""
  subprocess.run(['node','-e',program,json.dumps(m.COPY_METHOD)],cwd=ROOT,check=True)
 def test_source_drift_rejected(self):
  source=(ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text()
  for marker in ['private maybeStart(): void {','private async run(): Promise<void> {','aboutToDisappear(): void {','Stack({ alignContent: Alignment.TopStart }) {',"private record(event: string, value: string = ''): void {",'Text(this.status)']:
   with self.assertRaises(ValueError):m.with_capture(source.replace(marker,'changed'))
 def test_double_wrap_rejected(self):
  source=(ROOT/'fixtures/normal-core-consumer/recovery-fence/Index.ets').read_text()
  with self.assertRaises(ValueError):m.with_capture(m.with_capture(source))
if __name__=='__main__':unittest.main()
