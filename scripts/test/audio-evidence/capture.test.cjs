// 执行真实录制生命周期；系统录音为替身，不能计作设备音频证据。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let calls, handler, errorHandler, fake, closed;
const original = Module._load;
Module._load = function(name, parent, main) {
  if (name === '@kit.MediaKit') return {media:{createAVScreenCaptureRecorder:async()=>fake}};
  if (name === '@kit.CoreFileKit') return {fileIo:{OpenMode:{CREATE:1,READ_WRITE:2,TRUNC:4},
    openSync:()=>({fd:91}),closeSync:()=>{closed++;calls.push('fd-close');}}};
  return original.call(this,name,parent,main);
};
require.extensions['.ets'] = (m,file)=>m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file);
const {AudioCapture} = require(path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/AudioCapture.ets'));
function setup(overrides={}) {
  calls=[];closed=0;handler=undefined;errorHandler=undefined;
  fake={on:(event,cb)=>{if(event==='stateChange')handler=cb;else errorHandler=cb;},
    init:async(config)=>{assert.equal(config.fd,91);calls.push('init');},
    setMicEnabled:async(value)=>{assert.equal(value,false);calls.push('mic-off');handler(6);},
    startRecording:async()=>{calls.push('start');},stopRecording:async()=>{calls.push('stop');},
    release:async()=>{calls.push('release');},...overrides};
  return new AudioCapture((event,value)=>calls.push(event+':'+value));
}
const turn=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  let capture=setup(),resolved=false;
  let pending=capture.start('/tmp/fake.mp4',100).then(()=>{resolved=true;});
  await turn();assert.equal(resolved,false,'start API完成不等于系统已经录制');
  handler(0);await pending;capture.assertRecording();
  assert(capture.startedAt>0);
  for (const stage of ['create-call','create-returned','init-call','init-returned','mic-off-call','mic-off-returned','start-call','start-returned','waiting-started']) assert(calls.includes('capture-stage:'+stage),stage);
  await capture.finish();await capture.finish();
  for (const stage of ['stop-call','stop-returned','release-call','release-returned']) assert(calls.includes('capture-stage:'+stage),stage);
  assert.equal(closed,1);assert(calls.indexOf('stop')<calls.indexOf('release'));
  assert(calls.indexOf('release')<calls.indexOf('fd-close'));
  await assert.rejects(capture.start('/tmp/fake.mp4'),/ONE_SHOT/);

  capture=setup();pending=capture.start('/tmp/fake.mp4',100);await turn();handler(1);
  await assert.rejects(pending,/STATE_1/);assert.equal(closed,1);
  handler(0);assert.throws(()=>capture.assertRecording(),/STATE_1/);

  capture=setup();await assert.rejects(capture.start('/tmp/fake.mp4',5),/START_TIMEOUT/);assert.equal(closed,1);
  handler(0);assert.equal(capture.startedAt,0);

  capture=setup({init:async()=>{throw Error('INIT_FAILED');}});
  await assert.rejects(capture.start('/tmp/fake.mp4'),/INIT_FAILED/);assert.equal(closed,1);

  capture=setup();pending=capture.start('/tmp/fake.mp4',100);await turn();handler(0);await pending;
  handler(2);assert.throws(()=>capture.assertRecording(),/STATE_2/);
  await assert.rejects(capture.finish(),/STATE_2/);assert.equal(closed,1);

  capture=setup();pending=capture.start('/tmp/fake.mp4',100);await turn();handler(0);await pending;
  errorHandler({code:5400105});await assert.rejects(capture.finish(),/5400105/);assert.equal(closed,1);

  capture=setup({release:async()=>{calls.push('release');throw Error('RELEASE_FAILED');}});
  pending=capture.start('/tmp/fake.mp4',100);await turn();handler(0);await pending;
  await assert.rejects(capture.finish(),/RELEASE_FAILED/);assert(calls.includes('capture-stage:release-call'));assert(!calls.includes('capture-stage:release-returned'));assert.equal(closed,0,'未确认release不得关闭仍可能使用的fd');
  await assert.rejects(capture.finish(),/RELEASE_FAILED/);

  capture=setup({stopRecording:async()=>{throw Error('STOP_FAILED');}});
  pending=capture.start('/tmp/fake.mp4',100);await turn();handler(0);await pending;
  await assert.rejects(capture.finish(),/STOP_FAILED/);assert.equal(closed,1);
  let completeInit;
  capture=setup({init:()=>new Promise(resolve=>{completeInit=resolve;})});
  pending=capture.start('/tmp/fake.mp4',100);
  const startupRejected=assert.rejects(pending,/CANCELLED/);
  await turn();const ending=capture.finish();const endingRejected=assert.rejects(ending,/CANCELLED/);
  await turn();assert(calls.includes('capture-stage:init-call'));assert(!calls.includes('capture-stage:init-returned'));assert.equal(closed,0,'初始化未归还时不得抢先释放录制器/fd');
  completeInit();await startupRejected;await endingRejected;assert(calls.includes('capture-stage:init-returned'));
  assert(!calls.includes('start'),'页面离开后不得迟到开始录屏');assert.equal(closed,1);
  console.log('PASS: 9组录制生命周期回归（非设备验收）');
})().catch(error=>{console.error(error);process.exitCode=1;});
