// 真实 PlayerSession/桥/状态机，平台 NAPI 为可控替身。
const assert=require('node:assert/strict'),fs=require('node:fs'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let next=0,releases=0,registrationFailure=false;const callbacks=new Map(),failed=new Set();
const native=new Proxy({getRuntimeStatus:()=>JSON.stringify({state:'ready'}),
 createSession:async()=>({ok:true,handle:++next,code:'OK'}),
 setEventCallback:(h,cb)=>{if(registrationFailure)return {ok:false,handle:h,code:'CALLBACK_RESOURCE_LIMIT'};callbacks.set(h,cb);return {ok:true,handle:h,code:'OK'};},
 releaseSession:async h=>{releases++;callbacks.delete(h);return {ok:true,handle:h,code:'RELEASED'};},
},{get:(o,k)=>o[k]||((h)=>({ok:!failed.has(h),handle:h,code:failed.has(h)?'PLAYER_EVENT_QUEUE_FULL':'OK'}))});
const original=Module._load;Module._load=function(n,p,m){if(n==='libvidall_player_native.so')return {__esModule:true,default:native};if(n==='@kit.ArkTS')return {util:{}};return original.call(this,n,p,m);};
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {SessionStateMachine}=require('../../../packages/vidall-player/src/main/ets/internal/stateMachine.ets');
const {createNativePlayerBridge}=require('../../../packages/vidall-player/src/main/ets/native/nativeBridge.ets');
const {createPlayer}=require('../../../packages/vidall-player/src/main/ets/public/player.ets');
async function main(){
 const player=createPlayer(),events=[];player.subscribe(e=>events.push(e));
 await player.attachSurface({componentId:'a',generation:1,width:10,height:10});
 await player.load({kind:'localFile',uri:'file:///a.mp4'});failed.add(1);
 callbacks.get(1)({type:'error',message:'PLAYER_EVENT_QUEUE_FULL',eventEpoch:1,sequence:100,surfaceGeneration:1});
 const error=events.find(e=>e.type==='error').error;
 assert.equal(error.code,'PLAYER_EVENT_QUEUE_FULL');assert.match(error.message,/重新打开/);
 await assert.rejects(player.load({kind:'localFile',uri:'file:///b.mp4'}),e=>e.playerError?.code==='PLAYER_EVENT_QUEUE_FULL');
 await player.release();assert.equal(releases,1);
 const fresh=createPlayer();await fresh.attachSurface({componentId:'b',generation:1,width:10,height:10});
 await fresh.load({kind:'localFile',uri:'file:///b.mp4'});await fresh.release();assert.equal(releases,2);
 const cross=createPlayer(),crossEvents=[];cross.subscribe(e=>crossEvents.push(e));
 await cross.attachSurface({componentId:'cross',generation:1,width:10,height:10});
 await cross.load({kind:'localFile',uri:'file:///a.mp4'});const crossHandle=next;
 failed.add(crossHandle);
 await assert.rejects(cross.load({kind:'localFile',uri:'file:///b.mp4'}),e=>e.playerError?.code==='PLAYER_EVENT_QUEUE_FULL');
 callbacks.get(crossHandle)({type:'error',message:'PLAYER_EVENT_QUEUE_FULL',eventEpoch:1,sequence:100,surfaceGeneration:1});
 assert.equal(crossEvents.filter(e=>e.type==='error'&&e.error.code==='PLAYER_EVENT_QUEUE_FULL').length,1);
 assert.equal(crossEvents.filter(e=>e.type==='state').at(-1).state,'error');
 failed.delete(crossHandle);
 await assert.rejects(cross.load({kind:'localFile',uri:'file:///c.mp4'}),e=>e.playerError?.code==='PLAYER_EVENT_QUEUE_FULL');
 await cross.release();
 const logs=[],originalError=console.error;console.error=(message)=>logs.push(message);
 try {
  const state=new SessionStateMachine(),received=[];
  state.subscribe(()=>{throw new Error('private user data');});state.subscribe(e=>received.push(e.type));
  assert.doesNotThrow(()=>state.transition('preparing'));assert.deepEqual(received,['state']);
  const bridge=createNativePlayerBridge(),bridgeEvents=[];
  await bridge.attachSurface({componentId:'listeners',generation:1,width:10,height:10});const bridgeHandle=next;
  bridge.subscribe(()=>{throw new Error('private user data');});bridge.subscribe(e=>bridgeEvents.push(e.type));
  callbacks.get(bridgeHandle)({type:'fileEnd',message:'0',eventEpoch:1,sequence:1,surfaceGeneration:1});
  assert.deepEqual(bridgeEvents,['fileEnd']);assert.equal(logs.length,2);
  assert(!logs.some(line=>line.includes('private user data')));await bridge.release();
 } finally {console.error=originalError;}
 const beforeLimited=releases;
 registrationFailure=true;const limited=createPlayer();
 await assert.rejects(limited.attachSurface({componentId:'c',generation:1,width:10,height:10}),e=>e.playerError?.code==='CALLBACK_RESOURCE_LIMIT');
 assert.equal(releases,beforeLimited+1);await assert.rejects(limited.release());
 console.log('PASS callback overflow release/new session');
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
