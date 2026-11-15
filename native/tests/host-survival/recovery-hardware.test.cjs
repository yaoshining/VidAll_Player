// 执行诊断页的真实模式选择、资格断言及 run 方法，防止软件回退冒充硬件验收。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const root = path.resolve(__dirname, '../../..');
require.extensions['.ets'] = (m, f) => m._compile(ts.transpileModule(fs.readFileSync(f, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText, f);
const { initialMode, requireHardware, requireSoftware, requireSoftwareDecode } = require(root + '/fixtures/normal-core-consumer/recovery-terminal/ProbeChecks.ets');
const field = (value, source) => ({status:'available', value, source, estimated:false});
const snapshot = (backend='vulkan', decoder='ohcodec') => ({schemaVersion:1, fields:{
  renderBackend:field(backend,'session.actual-render-backend'), hardwareDecoder:field(decoder,'hwdec-current'),
  positionMs:field(1000,'time-pos')
}});
assert.equal(initialMode('hardware-first',1),'standard');
assert.equal(initialMode('software-control',1),'compatible');
for (const profile of ['hardware-first','software-control']) {
  for (const generation of [2,3]) assert.equal(initialMode(profile,generation),'compatible');
}
assert.throws(() => initialMode('unknown',1), /INVALID_PROBE_PROFILE/);
requireHardware(snapshot());
requireSoftware(snapshot('software','no'));
requireSoftwareDecode(snapshot('vulkan','no'));
for (const [backend, decoder] of [['software','no'],['vulkan','no'],['opengles','ohcodec'],['vulkan','ohcodec-copy']]) {
  assert.throws(() => requireHardware(snapshot(backend,decoder)), /HARDWARE_PATH_REQUIRED/);
}
for (const property of ['renderBackend','hardwareDecoder']) {
  for (const status of ['unavailable','unsupported','error']) {
    const s=snapshot();s.fields[property].status=status;
    assert.throws(() => requireHardware(s), /HARDWARE_PATH_REQUIRED/);
  }
  for (const mutate of [f=>{f.estimated=true;}, f=>{delete f.value;}, f=>{f.source='configured-option';}]) {
    const s=snapshot();mutate(s.fields[property]);assert.throws(() => requireHardware(s), /HARDWARE_PATH_REQUIRED/);
  }
}
assert.throws(() => requireHardware({...snapshot(),freshness:'cached-terminal'}), /HARDWARE_PATH_REQUIRED/);
assert.throws(() => requireSoftware(snapshot('vulkan','no')), /SOFTWARE_PATH_REQUIRED/);
assert.throws(() => requireSoftwareDecode(snapshot()), /SOFTWARE_DECODE_REQUIRED/);

function method(name, dependencies = {}) {
  const src=fs.readFileSync(root+'/fixtures/normal-core-consumer/recovery-terminal/Index.ets','utf8');
  const prefix=src.includes('  private async '+name+'(')?'  private async ':'  private ';
  const start=src.indexOf(prefix+name+'(');assert.ok(start>=0,name);
  const end=src.indexOf('\n  }',start)+4;assert.ok(end>start);
  const body=src.slice(start,end).replace(prefix+name,(prefix.includes('async')?'async ':'')+'function '+name);
  const js=ts.transpileModule(body,{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText;
  return new Function(...Object.keys(dependencies),js+'; return '+name+';')(...Object.values(dependencies));
}
(async()=>{
  const event=method('event');
  const current={cancelled:false,playerGeneration:2,firstFrames:0,record:()=>{}};
  event.call(current,{type:'firstFrame',surfaceGeneration:1},1);
  assert.equal(current.firstFrames,0,'A 的迟到首帧不得完成 B 的等待');
  event.call(current,{type:'state',state:'playing'},1);
  assert.equal(current.playerState,undefined,'A 的迟到状态不得推进 B');
  event.call(current,{type:'firstFrame',surfaceGeneration:2},2);
  assert.equal(current.firstFrames,1);
  // 全局锁仍 terminal 时，新恢复会话退出页面必须释放；仅第一代可接受旧会话拒绝。
  const finish=method('finish',{window:{getLastWindow:async()=>({setWindowKeepScreenOn:async()=>{},getWindowProperties:()=>({isKeepScreenOn:false})})},getPlayerRuntimeStatus:()=>({state:'terminal'})});
  let releases=0;
  await finish.call({context:{},playerGeneration:2,player:{release:async()=>{releases++;}},record:()=>{}});
  assert.equal(releases,1,'全局 terminal 不能跳过新兼容会话释放');
  const old={context:{},playerGeneration:1,player:{release:async()=>{throw Error('PLAYER_TERMINAL');}},record:()=>{}};
  await finish.call(old); assert.equal(old.player,undefined);
  await assert.rejects(()=>finish.call({context:{},playerGeneration:2,player:{release:async()=>{throw Error('OTHER_FAILURE');}},record:()=>{}}),/OTHER_FAILURE/);
  // 初始化挂起期间离页，不能在恢复后注册终局/故障监听器。
  let resumeInit;
  const initWait=new Promise(resolve=>{resumeInit=resolve;});
  const prepare=method('prepare',{fs:{accessSync:()=>true,OpenMode:{},open:async()=>({fd:1}),write:async()=>{},close:async()=>{}},
    initializePlayerRuntime:()=>initWait,getPlayerRuntimeStatus:()=>({state:'ready'}),
    onPlayerTerminal:()=>assert.fail('取消后不得注册终局监听'),onPlayerFault:()=>assert.fail('取消后不得注册故障监听')});
  const preparing={cancelled:false,getUIContext:()=>({getHostContext:()=>({filesDir:'/probe',resourceManager:{getRawFileContent:async()=>new Uint8Array([1])}})}),record:()=>{},maybeStart:()=>assert.fail('取消后不得启动')};
  const prepared=prepare.call(preparing);await new Promise(resolve=>setImmediate(resolve));
  preparing.cancelled=true;resumeInit();await prepared;
  const modes=[], surfaces=[];
  const open=method('open',{initialMode,createPlayer:options=>{modes.push(options.playbackMode);return {
    attachSurface:async value=>{surfaces.push(value.componentId);},load:async()=>{},play:async()=>{}
  };}});
  for(const profile of ['hardware-first','software-control']) {
    const context={active:()=>{},profile,controller:{getXComponentSurfaceId:()=> 'old'},recoveryController:{getXComponentSurfaceId:()=> 'new'},thirdController:{getXComponentSurfaceId:()=> 'third'},
      root:'probe',firstFrames:0,delay:async()=>{context.playerState='playing';},firstFrameAfter:async()=>{}};
    for(const gen of [1,2,3])await open.call(context,gen);
  }
  assert.deepEqual(surfaces,['old','new','third','old','new','third'],'每个实例需要独立 Surface');
  assert.deepEqual(modes,['standard','compatible','compatible','compatible','compatible','compatible']);
  let runtimeRead=false;
  const run=method('run',{requireHardware,requireSoftware,getPlayerRuntimeStatus:()=>{runtimeRead=true;return {state:'ready'};}});
  const records=[];const context={active:()=>{},profile:'hardware-first',open:async()=>({getDiagnostics:async()=>snapshot('software','no')}),record:(...x)=>records.push(x)};
  await assert.rejects(()=>run.call(context),/HARDWARE_PATH_REQUIRED/);
  assert.equal(runtimeRead,false,'未证明硬件时不能继续终局恢复流程');
  assert.equal(records.some(x=>x[0]==='summary'),false,'软件回退不得产出硬件成功摘要');
  for (const profile of ['hardware-first','software-control']) {
    let position=0;const accepted=[];
    let allowNavigation; const navigationGate=new Promise(resolve=>{allowNavigation=resolve;});
    const good=method('run',{requireHardware,requireSoftware,getPlayerRuntimeStatus:()=>({state:'terminal',recovery:{state:'ready',generation:2}})});
    const state={active:()=>{},waitForRecoveryNavigation:()=>navigationGate,profile,firstFrames:0,errors:0,firstIdentity:{sessionId:'1',loadGeneration:'1'},
      fault:{attribution:{state:'known',sessionId:'1',loadGeneration:'1'}},
      controller:{getXComponentSurfaceId:()=> 'old'},recoveryController:{getXComponentSurfaceId:()=> 'new'},thirdController:{getXComponentSurfaceId:()=> 'third'},
      recoverySurfaceReady:true,thirdSurfaceReady:true,delay:async()=>{},number:f=>f.value,record:(...x)=>accepted.push(x),finish:async()=>{},
      open:async generation=>{
        state.firstFrames++;
        return {play:async()=>{throw Error('PLAYER_TERMINAL');},release:async()=>{if(generation===1)throw Error('PLAYER_TERMINAL');},
          getDiagnostics:async()=>{const s=snapshot(generation===1&&profile==='hardware-first'?'vulkan':'software',generation===1&&profile==='hardware-first'?'ohcodec':'no');s.fields.positionMs.value=(position+=800);return s;}};
      }};
    const running=good.call(state);await new Promise(resolve=>setImmediate(resolve));
    assert.equal(state.firstFrames,1,'未完成用户导航前不得打开第二会话');
    allowNavigation();await running;
    const summary=JSON.parse(accepted.find(x=>x[0]==='summary')[1]);
    assert.equal(summary.profile,profile);assert.equal(summary.scope,'timer-global');assert.equal(summary.firstFrames,3);
    accepted.length=0;state.firstFrames=0;
    state.finish=async()=>{throw Error('KEEP_SCREEN_NOT_RELEASED');};
    await assert.rejects(()=>good.call(state),/KEEP_SCREEN_NOT_RELEASED/);
    assert.equal(accepted.some(x=>x[0]==='summary'),false,'清理不通过不得记录成功摘要');
  }
  const cancelledOpen=method('open',{initialMode,createPlayer:()=>assert.fail('取消后不得创建会话')});
  await assert.rejects(()=>cancelledOpen.call({active:()=>{throw Error('PROBE_CANCELLED');}},2),/PROBE_CANCELLED/);
  console.log('PASS 真实模式选择、诊断资格与页面拒绝软件冒充硬件');
})().catch(e=>{console.error(e);process.exitCode=1;});
