// 真实 PlayerSession / bridge，验证身份在原生提交前绑定到具体 load 调用。
const assert=require('node:assert/strict'),fs=require('node:fs'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let state='ready',recovery,faults=[];let nativeLoads=[];let loadHook;
const native=new Proxy({
 getRuntimeStatus:()=>JSON.stringify({state,recovery,faults,terminal:state==='terminal'?{stage:1,platformError:-7,ownerTag:'1',firstObservedMs:1,deadlineMs:3000}:undefined}),
 createSession:async()=>({ok:true,handle:17,code:'OK'}),
 load:async(...args)=>{nativeLoads.push(args);return loadHook?loadHook(args):{ok:true,handle:17,code:'OK'};},
}, {get:(o,k)=>o[k]||(()=>({ok:true,handle:17,code:'OK'}))});
const original=Module._load;
Module._load=function(n,p,m){if(n==='libvidall_player_native.so')return {__esModule:true,default:native};if(n==='@kit.ArkTS')return {util:{}};return original.call(this,n,p,m);};
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {createPlayer}=require('../../../packages/vidall-player/src/main/ets/public/player.ets');
const runtime=require('../../../packages/vidall-player/src/main/ets/public/runtime.ets');
const tick=()=>new Promise(r=>setImmediate(r));
const A={kind:'localFile',uri:'file:///A.mp4'},B={kind:'localFile',uri:'file:///B.mp4'};
(async()=>{
 const which=process.argv[2];const player=createPlayer();await player.attachSurface({componentId:'view',generation:1,width:10,height:10});
 if(which==='switch'){
  const map=new Map();let finish;
  loadHook=args=>{const key='17/'+args[5];assert(map.has(key),'原生调用前必须已交付身份');return args[1]===A.uri?new Promise(r=>finish=r):{ok:true,handle:17,code:'OK'};};
  const a=player.load(A,id=>{assert.equal(id.sessionId,'17');map.set(id.sessionId+'/'+id.loadGeneration,'A');});
  const b=player.load(B,id=>map.set(id.sessionId+'/'+id.loadGeneration,'B'));
  await tick();assert.equal(map.size,1);assert.equal(nativeLoads.length,1);finish({ok:true,handle:17,code:'OK'});await a;await b;
  assert.deepEqual(nativeLoads.map(x=>x[5]),[1,2]);assert.deepEqual([...map.values()],['A','B']);
  await player.release();let owner;
  runtime.onPlayerFault(f=>{owner=map.get(f.attribution.sessionId+'/'+f.attribution.loadGeneration);});
  faults=[{sequence:1,kind:'session-quarantined',stage:2,platformError:-7,attribution:{state:'known',sessionId:'17',loadGeneration:'1'}}];runtime.getPlayerRuntimeStatus();assert.equal(owner,'A');
 }else if(which==='queue-failed'){
  const ids=[];loadHook=()=>({ok:false,handle:17,code:'NATIVE_WORK_QUEUE_FULL'});
  await assert.rejects(player.load(A,id=>ids.push(id)),/原生操作失败|NATIVE_WORK_QUEUE_FULL/);
  loadHook=undefined;await player.load(B,id=>ids.push(id));
  assert.deepEqual(ids.map(x=>x.loadGeneration),['1','2']);assert.deepEqual(nativeLoads.map(x=>x[5]),[1,2]);
 }else if(which==='callback-failed'){
  await assert.rejects(player.load(A,()=>{throw Error('binding unavailable');}),e=>e.playerError?.code==='LOAD_IDENTITY_REJECTED');
  assert.equal(nativeLoads.length,0);let id;await player.load(B,value=>id=value);assert.equal(id.loadGeneration,'2');assert.equal(nativeLoads[0][5],2);
 }else if(which==='terminal-in-callback'){
  await assert.rejects(player.load(A,()=>{state='terminal';recovery={state:'pending',generation:0};runtime.getPlayerRuntimeStatus();}),/PLAYER_TERMINAL/);
  assert.equal(nativeLoads.length,0);
 }else if(which==='invalid'){
  let count=0;await assert.rejects(player.load({...A,uri:''},()=>count++));assert.equal(count,0);assert.equal(nativeLoads.length,0);
  let id;await player.load(A,value=>id=value);assert.equal(id.loadGeneration,'1');
 }else if(which==='legacy'){
  await player.load(A);assert.equal(nativeLoads[0][5],1);
 }else throw Error('unknown test');
 console.log('PASS',which);process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
