// 执行真实 PlayerSession / public createPlayer；仅替换平台 NAPI，不替代会话实现。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let state = 'unconfigured';
let recovery,configuredPolicy,requestedGeneration;
let faults=[];
let creates = 0, configurations = 0, nativeReleases = 0, callbackFailure = false;
const native = new Proxy({
  getRuntimeStatus: () => JSON.stringify({state, recovery, faults, terminal: state === 'terminal' ? {stage:1,platformError:-4,firstObservedMs:100,deadlineMs:3000,ownerTag:'1'} : undefined}),
  configureRuntime: async (_root,_text,_deadline,policy) => { configuredPolicy=policy;configurations++;state='ready'; return {ok:true,handle:0,code:'OK'}; },
  rejectRuntimeResources:()=>{state='failed';return {ok:false,handle:0,code:'RUNTIME_RESOURCE_FAILED'};},
  createSession: async (...args) => {requestedGeneration=args[5];creates++;return {ok:true,handle:1,code:'OK'};},
  setEventCallback:()=>({ok:!callbackFailure,handle:1,code:callbackFailure?'NATIVE_PLAYBACK_FAILED':'OK'}),
  releaseSession:async()=>{nativeReleases++;return {ok:true,handle:1,code:'RELEASED'};},
}, {get:(o,k)=>o[k]||(()=>({ok:true,handle:1,code:'OK'}))});
const load = Module._load;
Module._load = function(n,p,m) {
  if(n==='libvidall_player_native.so') return {__esModule:true,default:native};
  if(n==='@kit.ArkTS') return {util:{TextDecoder:class{decodeToString(b){return new TextDecoder().decode(b);}}}};
  return load.call(this,n,p,m);
};
require.extensions['.ets']=(m,f)=>{
  let source=fs.readFileSync(f,'utf8');
  // 只在测试编译中观测实际全局注册表，不给产品增加调试接口，也不依赖不确定的 GC 时机。
  if(f.endsWith('/public/runtime.ets')) source+='\nexport function testTerminalListenerCount(): number { return listeners.length; }';
  m._compile(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
};
const {PlayerSession}=require('../../packages/vidall-player/src/main/ets/internal/playerSession.ets');
const {createPlayer}=require('../../packages/vidall-player/src/main/ets/public/player.ets');
const runtime=require('../../packages/vidall-player/src/main/ets/public/runtime.ets');
const tick=()=>new Promise(r=>setImmediate(r));
async function bounded(p){return Promise.race([p,new Promise((_,r)=>setTimeout(()=>r(Error('TEST_TIMEOUT')),150))]);}
async function main(){
  const which=process.argv[2];
  if(which.startsWith('terminal-publication-')) {
    const preserve=which.endsWith('preserve');
    const reentrant=which.includes('reentrant');
    let poll,clears=0,reads=0,terminal;
    global.setInterval=fn=>{poll=fn;return 47;};
    global.clearInterval=id=>{assert.equal(id,47);clears++;};
    native.getRuntimeStatus=()=>{reads++;return JSON.stringify({state,terminal,recovery,faults});};
    const context={filesDir:'/private/app',resourceManager:{getRawFileContent:async()=>new TextEncoder().encode('[global]\nclient min protocol = SMB2_02\n')}};
    await runtime.initializePlayerRuntime(context,{terminalPolicy:preserve?'preserve-host':'controlled-app-exit',deadlineMs:3000});
    const bridge=new Proxy({subscribe:()=>()=>{},attachSurface:()=>new Promise(()=>{})}, {get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const player=new PlayerSession(undefined,bridge);
    const rejected=assert.rejects(bounded(player.attachSurface({componentId:'s',generation:1,width:1,height:1})),/PLAYER_TERMINAL/);
    const initial={stage:0,platformError:0,firstObservedMs:0,deadlineMs:3000,ownerTag:'0',attribution:{state:'unknown'}};
    const complete={stage:2,platformError:-7,firstObservedMs:123,deadlineMs:3000,ownerTag:'5',attribution:{state:'known',sessionId:'17',loadGeneration:'4'}};
    const early=[],late=[];let nested=0;
    runtime.onPlayerTerminal(info=>{
      early.push(info);
      if(reentrant) {
        terminal=complete;
        const refreshed=runtime.getPlayerRuntimeStatus();
        assert.equal(refreshed.terminal.firstObservedMs,123);
        runtime.onPlayerTerminal(info=>{nested++;late.push(info);});
      } else runtime.getPlayerRuntimeStatus();
    });
    runtime.onPlayerTerminal(()=>{throw Error('监听者失败不得阻止发布');});
    state='terminal';terminal=initial;
    if(preserve)recovery={state:'pending',generation:0};
    poll();await rejected;
    assert.equal(player.stateMachine.getState(),'error','元数据未发布也要立即终止旧会话');
    assert.equal(early.length,1);assert.equal(early[0].firstObservedMs,0);
    if(!reentrant)assert.equal(clears,0,'不完整元数据不能停止 controlled 策略的后续观察');
    terminal=complete;faults=[{sequence:1,kind:'process-terminal',stage:2,platformError:-7,attribution:complete.attribution}];
    if(preserve)recovery={state:'ready',generation:2};
    poll();
    const after=runtime.getPlayerRuntimeStatus();
    assert.deepEqual(after.terminal,complete,'已发布的完整记录必须更新暂态缓存');
    assert.equal(early.length,1,'同一监听者不得重复收到终局');
    runtime.onPlayerTerminal(info=>{late.push(info);assert.deepEqual(runtime.getPlayerRuntimeStatus().terminal,complete);});
    assert.equal(late.length,reentrant?2:1);assert(late.every(info=>info.firstObservedMs===123));
    assert.equal(nested,reentrant?1:0);assert.equal(runtime.testTerminalListenerCount(),0);
    assert.equal(clears,preserve?0:1);
    const lastReads=reads;runtime.getPlayerRuntimeStatus();
    assert.equal(reads,preserve?lastReads+1:lastReads,'controlled 完整记录才可停止原生读取');
  } else if(which==='terminal-listener-lifetime') {
    state='ready';recovery={state:'pending',generation:0};let a=0,b=0,c=0;
    const off=runtime.onPlayerTerminal(()=>{throw Error('已取消订阅不应执行');});off();off();
    runtime.onPlayerTerminal(()=>{a++;runtime.onPlayerTerminal(()=>c++);runtime.getPlayerRuntimeStatus();});
    runtime.onPlayerTerminal(()=>{b++;throw Error('listener');});
    assert.equal(runtime.testTerminalListenerCount(),2);
    state='terminal';runtime.getPlayerRuntimeStatus();
    assert.deepEqual([a,b,c],[1,1,1]);assert.equal(runtime.testTerminalListenerCount(),0,'终局投递后不能保留闭包');
    for(let i=0;i<100;i++) runtime.onPlayerTerminal(()=>c++);
    assert.equal(c,101);assert.equal(runtime.testTerminalListenerCount(),0,'终局后重放不能保留闭包');
  } else if(which==='failed-release-listener') {
    state='ready';native.createSession=async()=>({ok:false,handle:0,code:'NATIVE_SESSION_LIMIT'});
    for(let i=0;i<100;i++) {
      const player=createPlayer();
      await assert.rejects(player.attachSurface({componentId:'s',generation:1,width:1,height:1}));
      await assert.rejects(player.release());
      assert.equal(runtime.testTerminalListenerCount(),0,'创建失败且释放拒绝后不能保留 Player');
    }
    assert.equal(nativeReleases,0,'失败创建不伪造原生释放');
  } else if(which==='pending-release-listener') {
    state='ready';let finish;
    const bridge=new Proxy({subscribe:()=>()=>{},release:()=>new Promise(r=>finish=r)}, {get:(o,k)=>o[k]||(()=>Promise.resolve())});
    const player=new PlayerSession(undefined,bridge);const releasing=player.release();
    const rejected=assert.rejects(releasing,/PLAYER_TERMINAL/);
    assert.equal(runtime.testTerminalListenerCount(),1,'释放未结算时仍能收到终局');
    state='terminal';runtime.getPlayerRuntimeStatus();
    assert.equal(player.stateMachine.getState(),'error');finish();await rejected;
    assert.equal(runtime.testTerminalListenerCount(),0);
  } else if(which==='fault-notifications') {
    state='ready';const events=[];
    const off=runtime.onPlayerFault(f=>events.push(f));
    runtime.onPlayerFault(()=>{throw Error('listener failure');});
    const player=createPlayer();await player.release();
    faults=[{sequence:1,kind:'session-quarantined',stage:2,platformError:-7,attribution:{state:'known',sessionId:'17',loadGeneration:'4'}}];
    runtime.getPlayerRuntimeStatus();runtime.getPlayerRuntimeStatus();
    assert.equal(events.length,1);assert.equal(events[0].attribution.loadGeneration,'4');
    let replay=0;const stopReplay=runtime.onPlayerFault(()=>{replay++;runtime.getPlayerRuntimeStatus();});
    assert.equal(replay,1);
    faults.push({sequence:2,kind:'process-terminal',stage:3,platformError:-9,attribution:{state:'unknown'}});
    state='terminal';recovery={state:'ready',generation:2};runtime.getPlayerRuntimeStatus();
    assert.equal(events.length,2);assert.equal(replay,2);assert.equal(events[1].attribution.state,'unknown');
    off();stopReplay();faults.push({...faults[1],sequence:3});runtime.getPlayerRuntimeStatus();
    assert.equal(events.length,2);assert.equal(replay,2);
  } else if(which==='host-recovery') {
    const context={filesDir:'/private/app',resourceManager:{getRawFileContent:async()=>new TextEncoder().encode('[global]\nclient min protocol = SMB2_02\n')}};
    await runtime.initializePlayerRuntime(context,{terminalPolicy:'preserve-host',deadlineMs:3000});
    assert.equal(configuredPolicy,'preserve-host');
    const oldErrors=[];const old=createPlayer({playbackMode:'compatible',eventListener:e=>{if(e.type==='error')oldErrors.push(e.error);}});await old.attachSurface({componentId:'old',generation:1,width:10,height:10});assert.equal(requestedGeneration,1);
    state='terminal';recovery={state:'pending',generation:0};runtime.getPlayerRuntimeStatus();
    assert.equal(old.stateMachine.getState(),'error');
    assert.equal(oldErrors.length,1);assert(!oldErrors[0].message.includes('重新打开应用'));
    assert.throws(()=>createPlayer({playbackMode:'compatible'}),/PLAYER_RECOVERY_PENDING/);
    recovery={state:'ready',generation:2};
    assert.throws(()=>createPlayer(),/PLAYER_TERMINAL/);
    let freshEvent;native.setEventCallback=(_h,cb)=>{freshEvent=cb;return {ok:true,handle:1,code:'OK'};};
    const fresh=createPlayer({playbackMode:'compatible'});
    await fresh.attachSurface({componentId:'fresh',generation:1,width:10,height:10});assert.equal(requestedGeneration,2);
    await fresh.load({kind:'localFile',uri:'file:///test.mp4'});
    freshEvent({type:'state',message:'preparing',eventEpoch:1,sequence:1,surfaceGeneration:1});
    await fresh.play();
    freshEvent({type:'state',message:'playing',eventEpoch:1,sequence:2,surfaceGeneration:1});
    assert.equal(fresh.stateMachine.getState(),'playing');
    assert.notEqual(fresh.stateMachine.getState(),'error');
    await assert.rejects(old.play(),/PLAYER_TERMINAL/);
    await fresh.release();assert.equal(nativeReleases,1);
    assert.equal(runtime.getPlayerRuntimeStatus().state,'terminal');
  } else if(which==='bridge-callback-fail') {
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
    if(which==='fatal-queue' || which==='fatal-diagnostics') {player.attachSurface({componentId:'s',generation:1,width:1,height:1}).catch(e=>assert.match(e.message,/PLAYER_TERMINAL/));await tick();}
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
