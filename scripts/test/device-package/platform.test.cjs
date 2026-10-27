const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('../normal-core/node_modules/typescript');
const code=fs.readFileSync(path.resolve(__dirname,'../../../fixtures/device-smoke/entry/src/main/ets/smoke/PlatformPort.ets'),'utf8');const listeners=[],rows=[];const journal={record(...x){rows.push(x)}};
let runtimeState='ready';
const available=()=>({freshness:'live',fields:{positionMs:{status:'available',value:100},durationMs:{status:'available',value:30000},paused:{status:'available',value:false}}});
let diagnostics=async()=>available();
const sdk = {
 createPlayer(o) {
  listeners.push(o.eventListener);
  return {
   async attachSurface() {}, async load() { o.eventListener({type:'state',state:'preparing'}); },
   async play() {}, async release() {},
   async getDiagnostics() { return diagnostics(); }
  };
 },
 getPlayerRuntimeStatus() { return {state:runtimeState}; }
};
const box={exports:{},setTimeout,Promise,require(name){if(name==='@vidall/player')return sdk;if(name==='./LaunchSession')return {LaunchSession:{files:{root:'/approved-session'},journal}};return {}}};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText,box);
(async()=>{const p=new box.exports.PlatformPort({},'surface');await p.open(1);listeners[0]({type:'firstFrame',surfaceGeneration:1,sequence:1});assert.equal((await p.sample()).frames,1);await p.release();await p.open(2);listeners[0]({type:'firstFrame',surfaceGeneration:1,sequence:2});listeners[0]({type:'state',state:'completed'});listeners[1]({type:'firstFrame',surfaceGeneration:1,sequence:3});const a=await p.sample();assert.equal(a.frames,1,'旧cycle/错误generation不得提供新首帧');assert.equal(a.completed,false);listeners[1]({type:'firstFrame',surfaceGeneration:2,sequence:4});assert.equal((await p.sample()).frames,2);let cases=3;const failures=[];
async function check(name,fn){runtimeState='ready';diagnostics=async()=>available();try{await fn();cases++;}catch(e){failures.push({name,error:e.message});}}
async function port(){const x=new box.exports.PlatformPort({},'surface');await x.open(1);return x;}
await check('terminal-before-read',async()=>{const x=await port();let calls=0;diagnostics=async()=>{calls++;return available();};runtimeState='terminal';await assert.rejects(()=>x.sample(),/PLAYER_TERMINAL/);assert.equal(calls,0);});
await check('terminal-over-stale',async()=>{const x=await port();let calls=0;diagnostics=async()=>{calls++;runtimeState='terminal';throw Error('DIAGNOSTICS_STALE');};await assert.rejects(()=>x.sample(),/PLAYER_TERMINAL/);assert.equal(calls,1);});
await check('release-over-stale',async()=>{const x=await port();diagnostics=async()=>{await x.release();throw Error('DIAGNOSTICS_STALE');};await assert.rejects(()=>x.sample(),/DIAGNOSTICS_RELEASED/);});
await check('new-cycle-refuses-old-response',async()=>{const x=await port();diagnostics=async()=>{await x.release();await x.open(2);return available();};await assert.rejects(()=>x.sample(),/DIAGNOSTICS_RELEASED/);});
await check('cached-terminal-not-live',async()=>{const x=await port();diagnostics=async()=>({...available(),freshness:'cached-terminal'});await assert.rejects(()=>x.sample(),/PLAYER_TERMINAL/);});
await check('cancel-during-unavailable-wait',async()=>{const x=await port();let cancelled=false,calls=0;x.sleep=async()=>{cancelled=true;};diagnostics=async()=>{calls++;return {fields:{positionMs:{status:'unavailable'},durationMs:{status:'unavailable'},paused:{status:'unavailable'}}};};await assert.rejects(()=>x.sample(()=>{if(cancelled)throw Error('SESSION_CANCELLED');}),/SESSION_CANCELLED/);assert.equal(calls,1);});
await check('cancel-before-first-query',async()=>{const x=await port();let calls=0;diagnostics=async()=>{calls++;return available();};await assert.rejects(()=>x.sample(()=>{throw Error('SESSION_CANCELLED');}),/SESSION_CANCELLED/);assert.equal(calls,0);});
await check('optional-freshness-absent',async()=>{const x=await port();diagnostics=async()=>{const v=available();delete v.freshness;return v;};assert.equal((await x.sample()).durationMs,30000);});
await check('completed-during-await-uses-same-cycle-near-tail',async()=>{const x=await port();diagnostics=async()=>({...available(),fields:{...available().fields,positionMs:{status:'available',value:29900}}});await x.sample();diagnostics=async()=>{listeners.at(-1)({type:'state',state:'completed'});return {fields:{positionMs:{status:'unavailable'},durationMs:{status:'unavailable'},paused:{status:'unavailable'}}};};x.sleep=async()=>{};const result=await x.sample();assert.equal(result.completed,true);assert.equal(result.positionMs,29900);});
await check('completed-without-near-tail-is-not-success',async()=>{const x=await port();await x.sample();listeners.at(-1)({type:'state',state:'completed'});await assert.rejects(()=>x.sample(),/EOF_WITHOUT_CYCLE_DIAGNOSTIC/);});
await check('completed-during-await-still-checks-terminal',async()=>{const x=await port();await x.sample();diagnostics=async()=>{listeners.at(-1)({type:'state',state:'completed'});runtimeState='terminal';return available();};await assert.rejects(()=>x.sample(),/PLAYER_TERMINAL/);});
for (const failure of ['release','cycle','cancel']) await check('completed-await-'+failure,async()=>{const x=await port();diagnostics=async()=>({...available(),fields:{...available().fields,positionMs:{status:'available',value:29900}}});await x.sample();let cancelled=false;diagnostics=async()=>{listeners.at(-1)({type:'state',state:'completed'});if(failure==='cancel')cancelled=true;else {await x.release();if(failure==='cycle')await x.open(2);}return available();};await assert.rejects(()=>x.sample(()=>{if(cancelled)throw Error('SESSION_CANCELLED');}),failure==='cancel'?/SESSION_CANCELLED/:/DIAGNOSTICS_RELEASED/);});
await check('new-cycle-cannot-use-previous-tail',async()=>{const x=await port();diagnostics=async()=>({...available(),fields:{...available().fields,positionMs:{status:'available',value:29900}}});await x.sample();await x.release();await x.open(2);listeners.at(-1)({type:'state',state:'completed'});await assert.rejects(()=>x.sample(),/EOF_WITHOUT_CYCLE_DIAGNOSTIC/);});
if(failures.length){console.error(JSON.stringify({failures,casesAttempted:cases+failures.length}));throw Error('platform guard regressions failed');}
console.log(JSON.stringify({passed:true,cases,scope:'真实PlatformPort事件闭包及生命周期守卫/模拟公共API'}));})().catch(e=>{console.error(e);process.exitCode=1});
