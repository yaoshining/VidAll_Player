// 执行真实 PlayerSession / public createPlayer；仅替换平台 NAPI，不替代会话实现。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let state = 'unconfigured';
let creates = 0, configurations = 0, nativeReleases = 0, callbackFailure = false;
const native = new Proxy({
  getRuntimeStatus: () => JSON.stringify({state, terminal: state === 'terminal' ? {stage:1,platformError:-4,firstObservedMs:100,deadlineMs:3000,ownerTag:'1'} : undefined}),
  configureRuntime: async () => { configurations++;state='ready'; return {ok:true,handle:0,code:'OK'}; },
  rejectRuntimeResources:()=>{state='failed';return {ok:false,handle:0,code:'RUNTIME_RESOURCE_FAILED'};},
  createSession: async () => {creates++;return {ok:true,handle:1,code:'OK'};},
  setEventCallback:()=>({ok:!callbackFailure,handle:1,code:callbackFailure?'NATIVE_PLAYBACK_FAILED':'OK'}),
  releaseSession:async()=>{nativeReleases++;return {ok:true,handle:1,code:'RELEASED'};},
}, {get:(o,k)=>o[k]||(()=>({ok:true,handle:1,code:'OK'}))});
const load = Module._load;
Module._load = function(n,p,m) {
  if(n==='libvidall_player_native.so') return {__esModule:true,default:native};
  if(n==='@kit.ArkTS') return {util:{TextDecoder:class{decodeToString(b){return new TextDecoder().decode(b);}}}};
  return load.call(this,n,p,m);
};
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {PlayerSession}=require('../../packages/vidall-player/src/main/ets/internal/playerSession.ets');
const {createPlayer}=require('../../packages/vidall-player/src/main/ets/public/player.ets');
const runtime=require('../../packages/vidall-player/src/main/ets/public/runtime.ets');
const tick=()=>new Promise(r=>setImmediate(r));
async function bounded(p){return Promise.race([p,new Promise((_,r)=>setTimeout(()=>r(Error('TEST_TIMEOUT')),150))]);}
async function main(){
  const which=process.argv[2];
  if(which==='bridge-callback-fail') {
    state='ready';callbackFailure=true;const {createNativePlayerBridge}=require('../../packages/vidall-player/src/main/ets/native/nativeBridge.ets');
    const bridge=createNativePlayerBridge();await assert.rejects(bridge.attachSurface({componentId:'s',generation:1,width:1,height:1}));await tick();assert.equal(nativeReleases,1);
  } else if(which==='bridge-create-fail') {
    state='ready';native.createSession=async()=>({ok:false,handle:0,code:'NATIVE_PLAYBACK_FAILED'});
    const {createNativePlayerBridge}=require('../../packages/vidall-player/src/main/ets/native/nativeBridge.ets');const bridge=createNativePlayerBridge();
    await assert.rejects(bridge.attachSurface({componentId:'s',generation:1,width:1,height:1}));await assert.rejects(bridge.release());assert.equal(nativeReleases,0);
  } else if(which==='bridge-pending-create') {
    state='ready';let finish,attached=0;native.createSession=()=>new Promise(r=>finish=r);native.attachSurface=async()=>{attached++;return {ok:true,handle:1,code:'OK'};};
    const {createNativePlayerBridge}=require('../../packages/vidall-player/src/main/ets/native/nativeBridge.ets');const bridge=createNativePlayerBridge();
    const attach=bridge.attachSurface({componentId:'s',generation:1,width:1,height:1});const release=bridge.release();await tick();assert.equal(attached,0);assert.equal(nativeReleases,0);
    finish({ok:true,handle:1,code:'OK'});await attach;await release;assert.equal(nativeReleases,1);await assert.rejects(bridge.attachSurface({componentId:'s',generation:2,width:1,height:1}));
  } else if(which==='bridge-callback-terminal') {
    state='ready';native.setEventCallback=()=>{state='terminal';return {ok:false,handle:1,code:'PLAYER_TERMINAL'};};
    const {createNativePlayerBridge}=require('../../packages/vidall-player/src/main/ets/native/nativeBridge.ets');const bridge=createNativePlayerBridge();
    await assert.rejects(bridge.attachSurface({componentId:'s',generation:1,width:1,height:1}));await tick();assert.equal(nativeReleases,0);await assert.rejects(bridge.release(),/PLAYER_TERMINAL/);
  } else if(which==='late-load') {
    state='ready';let finish,pushes=0;
    const bridge=new Proxy({subscribe:()=>()=>{},load:()=>new Promise(r=>finish=r),addExternalSubtitle:()=>{pushes++;return Promise.resolve();}}, {get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const player=new PlayerSession(undefined,bridge);await player.attachSurface({componentId:'s',generation:1,width:1,height:1});
    const pending=player.load({kind:'localFile',uri:'file:///test.mp4',externalSubtitles:[{uri:'file:///test.srt'}]});const rejected=assert.rejects(pending,/PLAYER_TERMINAL/);await tick();state='terminal';runtime.getPlayerRuntimeStatus();finish();await rejected;
    assert.equal(player.source,undefined);assert.equal(pushes,0);assert.equal(player.stateMachine.getState(),'error');
  } else if(which==='configure') {
    const context={filesDir:'/private/app',resourceManager:{getRawFileContent:async()=>new TextEncoder().encode('[global]\nclient min protocol = SMB2_02\n')}};
    const options={terminalPolicy:'controlled-app-exit',deadlineMs:3000};
    const a=runtime.initializePlayerRuntime(context,options),b=runtime.initializePlayerRuntime(context,options);
    assert.equal(a,b);await a;assert.equal(configurations,1);await runtime.initializePlayerRuntime(context,options);assert.equal(configurations,1);
    await assert.rejects(runtime.initializePlayerRuntime(context,{...options,deadlineMs:4000}),/RUNTIME_CONFIG_CONFLICT/);
  } else if(which==='resource-failed') {
    const context={filesDir:'/private/app',resourceManager:{getRawFileContent:async()=>{throw Error('missing');}}};
    const options={terminalPolicy:'controlled-app-exit',deadlineMs:3000};
    await assert.rejects(runtime.initializePlayerRuntime(context,options),/RUNTIME_RESOURCE_FAILED/);
    assert.equal(runtime.getPlayerRuntimeStatus().state,'failed');
    await assert.rejects(runtime.initializePlayerRuntime(context,options),/RUNTIME_RESOURCE_FAILED/);assert.equal(configurations,0);
  } else if(which==='constructor-terminal-replay') {
    state='ready';let reads=0;const events=[];
    // 首次 native 状态读取发生在 onPlayerTerminal 注册内，必须同步重放给调用方。
    const original=native.getRuntimeStatus;
    native.getRuntimeStatus=()=>{reads++;state='terminal';return original();};
    const bridge=new Proxy({subscribe:()=>()=>{}},{get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const player=new PlayerSession({eventListener:e=>events.push(e)},bridge);
    assert.equal(reads,1);assert.equal(player.stateMachine.getState(),'error');
    assert.deepEqual(events.map(e=>e.type),['state','error']);
    assert.equal(events[0].state,'error');assert.equal(events[1].error.code,'PLAYER_TERMINAL');
    runtime.getPlayerRuntimeStatus();runtime.getPlayerRuntimeStatus();assert.equal(events.length,2);
    const noListener=new PlayerSession(undefined,bridge);assert.equal(noListener.stateMachine.getState(),'error');
  } else if(which==='notifications') {
    state='ready';let a=0,b=0,c=0;runtime.onPlayerTerminal(()=>{a++;throw Error('listener');});runtime.onPlayerTerminal(()=>b++);
    state='terminal';const first=runtime.getPlayerRuntimeStatus().terminal;runtime.getPlayerRuntimeStatus();runtime.onPlayerTerminal(info=>{c++;assert.equal(info,first);});
    assert.deepEqual([a,b,c],[1,1,1]);
  } else if(which==='cached' || which==='late' || which==='released') {
    state='ready';let finish,reads=0;
    const bridge=new Proxy({subscribe:()=>()=>{},attachSurface:()=>new Promise(r=>finish=r),release:()=>Promise.resolve(),getDiagnostics:()=>{reads++;return Promise.resolve({schemaVersion:1,fields:{},sampledAtMs:7});}},{get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const a=new PlayerSession(undefined,bridge),b=new PlayerSession(undefined,bridge);const states=[];a.subscribe(e=>{if(e.type==='state')states.push(e.state);});
    if(which==='cached'){await a.getDiagnostics();state='terminal';const cached=await bounded(a.getDiagnostics());assert.equal(cached.freshness,'cached-terminal');assert.equal(cached.sampledAtMs,7);assert.equal(reads,1);}
    if(which==='late'){const pending=a.attachSurface({componentId:'new',generation:4,width:4,height:4});const rejected=assert.rejects(pending,/PLAYER_TERMINAL/);await tick();state='terminal';runtime.getPlayerRuntimeStatus();finish();await rejected;assert.equal(a.surface,undefined);}
    if(which==='released'){await a.release();state='terminal';runtime.getPlayerRuntimeStatus();assert.equal(a.stateMachine.getState(),'released');}else assert.equal(a.stateMachine.getState(),'error');
    assert.equal(b.stateMachine.getState(),'error');
  } else if(which==='unconfigured') {
    assert.throws(()=>createPlayer(), /RUNTIME_NOT_READY/);
    assert.equal(creates,0,'配置前禁止创建 mpv');
  } else {
    state='ready';let releases=0,commands=0;
    const bridge=new Proxy({subscribe:()=>()=>{},attachSurface:()=>new Promise(()=>{}),release:()=>{releases++;return Promise.resolve();},setPropertyString:()=>{commands++;return Promise.resolve();}}, {get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const player=new PlayerSession(undefined,bridge);
    if(which==='fatal-queue' || which==='fatal-diagnostics') {player.attachSurface({componentId:'s',generation:1,width:1,height:1});await tick();}
    state='terminal';
    if(which==='fatal-release') {
      await assert.rejects(bounded(player.release()),/PLAYER_TERMINAL/);assert.equal(releases,0);
    } else if(which==='fatal-diagnostics') {
      await assert.rejects(bounded(player.getDiagnostics()),/PLAYER_TERMINAL/);
    } else {
      await assert.rejects(bounded(player.setPropertyString('sid','1')),/PLAYER_TERMINAL/);assert.equal(commands,0);
    }
  }
  console.log('PASS '+which);
}
main().then(()=>process.exit(0),e=>{console.error(e.message);process.exit(1);});
