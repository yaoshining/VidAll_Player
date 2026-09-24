// 主机侧执行真实 ETS 会话代码；仅替换设备 NAPI 模块，不能替代真机验证。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const original = Module._load;
Module._load = function(name, parent, main) {
  if (name === '../native/nativeBridge') return { createNativePlayerBridge: () => { throw Error('mock required'); } };
  return original.call(this, name, parent, main);
};
require.extensions['.ets'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText, file);
const { PlayerSession } = require('../../packages/vidall-player/src/main/ets/internal/playerSession.ets');
const tick = () => new Promise(resolve => setImmediate(resolve));
async function main() {
  const path = require('node:path');
  const specs = fs.readFileSync(path.join(__dirname, '../diagnostics/properties.inc'), 'utf8');
  const declaration = fs.readFileSync(path.join(__dirname, '../../packages/vidall-player/src/main/ets/public/diagnostics.ets'), 'utf8');
  const nativeKeys = [...specs.matchAll(/\{"([^"\n]+)"/g)].map(m => m[1]);
  const apiFields = declaration.split('export interface PlayerDiagnosticsFields {')[1].split('}')[0];
  const publicKeys = [...apiFields.matchAll(/  (\w+): DiagnosticField/g)].map(m => m[1]);
  assert.deepEqual([...nativeKeys, 'renderBackend', 'surfaceWidth', 'surfaceHeight'].sort(), publicKeys.sort());
  let reads = 0, complete;
  const bridge = new Proxy({
    subscribe: () => () => {},
    getDiagnostics: () => { reads++; return new Promise(resolve => { complete = resolve; }); }
  }, { get: (o, key) => o[key] || (() => Promise.resolve()) });
  const player = new PlayerSession(undefined, bridge);
  let events = []; player.subscribe(e => events.push(e));
  await tick(); assert.equal(reads, 0);
  const a = player.getDiagnostics(), b = player.getDiagnostics();
  await tick(); assert.equal(reads, 1);
  complete({ schemaVersion: 1, fields: {} });
  assert.deepEqual(await a, await b);
  assert.equal(events.length, 0);
  for (const mutate of [
    () => player.attachSurface({ componentId: 'x', generation: 1, width: 1920, height: 1080 }),
    () => player.resizeSurface({ componentId: 'x', generation: 1, width: 1280, height: 720 }),
    () => player.detachSurface(1),
    () => player.load({kind:'https',uri:'https://example.test/video'}),
    () => player.stop()
  ]) {
    const pending = player.getDiagnostics();
    const rejection = assert.rejects(pending, /DIAGNOSTICS_STALE/);
    await tick(); const change = mutate();
    complete({schemaVersion:1,fields:{}});
    await rejection; await change;
  }
  for (let i = 0; i < 30; i++) {
    const snapshot = player.getDiagnostics(); await tick();
    complete({schemaVersion:1,fields:{}}); await snapshot;
  }
  const stoppedReads = reads; await tick(); await tick(); assert.equal(reads, stoppedReads);
  const pending = player.getDiagnostics();
  const stale = assert.rejects(pending, /DIAGNOSTICS_STALE/);
  await tick(); await player.release(); complete({schemaVersion:1,fields:{}}); await stale;
  await assert.rejects(player.getDiagnostics(), /DIAGNOSTICS_RELEASED/);
  const failed = new PlayerSession(undefined, new Proxy({subscribe:()=>()=>{},getDiagnostics:()=>Promise.reject(Error('read failed'))}, {get:(o,k)=>o[k]||(()=>Promise.resolve())}));
  let errors=0; failed.subscribe(e=>{if(e.type==='error')errors++;});
  await assert.rejects(failed.getDiagnostics(), /read failed/); assert.equal(errors,0);
  await assert.rejects(failed.getDiagnostics(), /read failed/); await failed.release();
  let nativeEvent;
  const frames=[];
  const surfacePlayer=new PlayerSession({eventListener:e=>frames.push(e)},new Proxy({subscribe:cb=>{nativeEvent=cb;return()=>{};}},{get:(o,k)=>o[k]||(()=>Promise.resolve())}));
  await surfacePlayer.attachSurface({componentId:'new-surface',generation:2,width:640,height:360});
  await surfacePlayer.load({kind:'localFile',uri:'file:///synthetic.mp4'});
  const epoch=1;
  nativeEvent({type:'state',message:'preparing',eventEpoch:epoch,surfaceGeneration:2,sequence:1});
  nativeEvent({type:'state',message:'playing',eventEpoch:epoch,surfaceGeneration:1,sequence:2});
  assert.equal(frames.filter(e=>e.type==='firstFrame').length,0);
  nativeEvent({type:'state',message:'playing',eventEpoch:epoch,surfaceGeneration:2,sequence:3});
  assert.equal(frames.find(e=>e.type==='firstFrame')?.surfaceGeneration,2);
  await surfacePlayer.release();
  console.log('诊断会话：并发合并、生命周期过期、释放后拒绝、错误隔离通过');
}
main().catch(e => {console.error(e);process.exitCode=1;});
