const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {runFocusProbe}=require(path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/FocusRun.ets'));
function setup(mode='ok') {
 const events=[];let alarm=false,started=false,recovered=false,reads=0,confirm;
 const port={active:()=>{},record:e=>events.push(e),delay:async()=>{},
  startAlarm:async()=>{alarm=true;started=true;events.push('start');},stopAlarm:async()=>{alarm=false;events.push('stop');},
  samplesWritten:()=>mode==='no-audio'?0:48000,
  snapshot:async()=>{reads++;return{paused:!started?false:(mode==='no-pause'?false:!recovered),positionMs:recovered?(mode==='stuck'?1000:2000):1000+(mode==='moving'?reads*500:0)};},
  confirmManualResume:()=>{events.push('manual');return new Promise(r=>{confirm=r;});},
  resume:async()=>{events.push('resume');recovered=true;}};
 return{port,events,confirm:()=>confirm()};
}
(async()=>{
 const x=setup();const p=runFocusProbe(x.port);await new Promise(r=>setImmediate(r));
 assert(x.events.includes('stop'));assert(!x.events.includes('resume'));
 x.confirm();await p;assert.deepEqual(x.events.filter(e=>['start','stop','manual','resume'].includes(e)),['start','stop','manual','resume']);
 for(const mode of ['no-audio','no-pause','moving']){const x=setup(mode);await assert.rejects(runFocusProbe(x.port));assert(x.events.includes('stop'));assert(!x.events.includes('resume'));}
 const stuck=setup('stuck');const failed=runFocusProbe(stuck.port);await new Promise(r=>setImmediate(r));stuck.confirm();await assert.rejects(failed,/RESUME_NOT_ADVANCING/);
 const cancelled=setup();cancelled.port.active=()=>{throw Error('CANCELLED');};await assert.rejects(runFocusProbe(cancelled.port),/CANCELLED/);assert(!cancelled.events.includes('start'));
 console.log('PASS: 真实焦点流程6组门槛，必须系统暂停且人工确认后恢复（平台为替身）');
})().catch(e=>{console.error(e);process.exitCode=1;});
