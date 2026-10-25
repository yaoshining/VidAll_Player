const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('../normal-core/node_modules/typescript');
const code=fs.readFileSync(path.resolve(__dirname,'../../../fixtures/device-smoke/entry/src/main/ets/smoke/PlatformPort.ets'),'utf8');const listeners=[],rows=[];const journal={record(...x){rows.push(x)}};
const sdk = {
 createPlayer(o) {
  listeners.push(o.eventListener);
  return {
   async attachSurface() {}, async load() { o.eventListener({type:'state',state:'preparing'}); },
   async play() {}, async release() {},
   async getDiagnostics() { return {fields:{positionMs:{status:'available',value:100},durationMs:{status:'available',value:30000},paused:{status:'available',value:false}}}; }
  };
 },
 getPlayerRuntimeStatus() { return {state:'ready'}; }
};
const box={exports:{},setTimeout,Promise,require(name){if(name==='@vidall/player')return sdk;if(name==='./LaunchSession')return {LaunchSession:{files:{root:'/approved-session'},journal}};return {}}};vm.runInNewContext(ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText,box);
(async()=>{const p=new box.exports.PlatformPort({},'surface');await p.open(1);listeners[0]({type:'firstFrame',surfaceGeneration:1,sequence:1});assert.equal((await p.sample()).frames,1);await p.release();await p.open(2);listeners[0]({type:'firstFrame',surfaceGeneration:1,sequence:2});listeners[0]({type:'state',state:'completed'});listeners[1]({type:'firstFrame',surfaceGeneration:1,sequence:3});const a=await p.sample();assert.equal(a.frames,1,'旧cycle/错误generation不得提供新首帧');assert.equal(a.completed,false);listeners[1]({type:'firstFrame',surfaceGeneration:2,sequence:4});assert.equal((await p.sample()).frames,2);console.log(JSON.stringify({passed:true,cases:3,scope:'真实PlatformPort事件闭包与模拟公共API'}));})().catch(e=>{console.error(e);process.exitCode=1});
