// 执行真实诊断流程模块；平台解码和人工日志确认是明确的替身，不代表设备验收。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const fixture = path.resolve(__dirname, '../../../fixtures/normal-core-consumer/recovery-fence');
const load = Module._load;
Module._load = function (name, parent, main) {
  if (name === './ProbeChecks' && parent.filename.startsWith(fixture)) {
    return load.call(this, path.join(fixture, '../recovery-terminal/ProbeChecks.ets'), parent, main);
  }
  return load.call(this, name, parent, main);
};
require.extensions['.ets'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText, file);
const { runFenceProbe, FenceFaultInbox } = require(path.join(fixture, 'FenceRun.ets'));

function actual(value, source) { return { status: 'available', estimated: false, value, source }; }
function snapshot(index) {
  return { schemaVersion: 1, freshness: 'live', fields: {
    renderBackend: actual('vulkan', 'session.actual-render-backend'),
    hardwareDecoder: actual(index === 4 ? 'no' : 'ohcodec', 'hwdec-current')
  } };
}
function fault(index, sequence) {
  return { sequence, kind: 'session-quarantined', platformError: -4, stage: 1,
    attribution: { state: 'known', sessionId: 'session-' + index, loadGeneration: '1' } };
}
function port(overrides = {}) {
  const events = [], inbox = new FenceFaultInbox();
  let confirm, pendingFault, releases = 0;
  const value = {
    inbox, events,
    runtimeState: () => 'ready',
    open: async index => {
      events.push('open-' + index);
      return { index, surfaceId: 'surface-' + index, identity: { sessionId: 'session-' + index, loadGeneration: '1' } };
    },
    snapshot: async session => snapshot(session.index),
    confirmPlayback: async session => events.push('playing-' + session.index),
    returnToList: async session => events.push('list-' + session.index),
    close: async session => {
      events.push('close-' + session.index); releases++;
      // 与真实 release 一致：接口完成不等于原生资源安全销毁。
      if (session.index === 1 || session.index === 3) {
        pendingFault = fault(session.index, session.index === 1 ? 1 : 2);
      }
    },
    nextFault: async sequence => {
      events.push('fault-after-' + sequence);
      // close 返回后才投递，模拟独立于已释放 Player 的运行时事件。
      inbox.add(pendingFault);
      return inbox.after(sequence);
    },
    faultCount: () => inbox.count(),
    confirmLateClose: () => {
      events.push('waiting-native-log');
      return new Promise(resolve => { confirm = resolve; });
    },
    record: (event, value = '') => events.push(event + (value ? ':' + value : '')),
    ...overrides
  };
  return { value, approve: () => { assert(confirm, '必须先到人工日志确认阶段'); confirm(); }, releases: () => releases };
}
const nextTurn = () => new Promise(resolve => setImmediate(resolve));
async function reachConfirmation(run) {
  const promise = runFenceProbe(run.value);
  await nextTurn();
  return { promise };
}

async function main() {
  const happy = port(), running = await reachConfirmation(happy);
  assert(happy.value.events.includes('waiting-native-log'));
  assert(!happy.value.events.includes('open-3'), '固定等待不得代替原生日志确认');
  assert.equal(happy.releases(), 2);
  happy.approve();
  await running.promise;
  assert.deepEqual(happy.value.events.filter(e => /^(open|close|playing)-\d$/.test(e)), [
    'open-1', 'playing-1', 'close-1', 'open-2', 'playing-2', 'close-2',
    'open-3', 'playing-3', 'close-3', 'open-4', 'playing-4', 'close-4'
  ]);
  assert.equal(happy.value.inbox.count(), 2);
  assert(happy.value.events.indexOf('list-1') < happy.value.events.indexOf('open-2'));
  assert(happy.value.events.includes('list-1'));
  assert(happy.value.events.includes('list-3'));
  assert(happy.value.events.includes('probe-flow-completed'));
  for (const mutate of [
    f => { f.platformError = -3; }, f => { f.stage = 2; },
    f => { f.kind = 'process-terminal'; }, f => { f.attribution.state = 'unknown'; },
    f => { f.attribution.sessionId = 'other'; }, f => { f.attribution.loadGeneration = '2'; }
  ]) {
    const bad = port({ nextFault: async () => { const f = fault(1, 1); mutate(f); return f; } });
    await assert.rejects(runFenceProbe(bad.value), /CLOSE_FAULT_MISMATCH/);
    assert(!bad.value.events.includes('open-2'));
  }
  const software = port({ snapshot: async () => snapshot(4) });
  await assert.rejects(runFenceProbe(software.value), /HARDWARE_PATH_REQUIRED/);
  assert.equal(software.releases(), 0);
  assert(software.value.events.some(e => e.startsWith('playback-observed:') && e.includes('"value":"no"')));
  assert(!software.value.events.some(e => e.startsWith('playback-path:')));
  const oldSurface = port({ open: async index => ({ index, surfaceId: 'same', identity: { sessionId: 'session-' + index, loadGeneration: '1' } }) });
  await assert.rejects(runFenceProbe(oldSurface.value), /FRESH_SURFACE_REQUIRED/);
  const oldSession = port({ open: async index => ({ index, surfaceId: 'surface-' + index, identity: { sessionId: 'session-1', loadGeneration: String(index) } }) });
  await assert.rejects(runFenceProbe(oldSession.value), /FRESH_SESSION_REQUIRED/);
  const runtime = port({ runtimeState: () => 'terminal' });
  await assert.rejects(runFenceProbe(runtime.value), /RUNTIME_NOT_READY/);
  assert.equal(runtime.value.events.length, 0);
  const neverReclaimed = port({ snapshot: async s => snapshot(s.index === 3 ? 4 : s.index) });
  const blocked = await reachConfirmation(neverReclaimed); neverReclaimed.approve();
  await assert.rejects(blocked.promise, /HARDWARE_PATH_REQUIRED/);
  assert(!neverReclaimed.value.events.includes('open-4'), '点击确认不能替代 C 的实际硬解检查');
  const overLimit = port({ snapshot: async s => snapshot(s.index === 4 ? 1 : s.index) });
  const overflow = await reachConfirmation(overLimit); overLimit.approve();
  await assert.rejects(overflow.promise, /SOFTWARE_DECODE_REQUIRED/);
  const unexpected = port(); const late = await reachConfirmation(unexpected);
  unexpected.value.inbox.add(fault(2, 2)); unexpected.approve();
  await assert.rejects(late.promise, /UNEXPECTED_FAULT_COUNT/);
  const inbox = new FenceFaultInbox(), source = fault(1, 1);
  inbox.add(source); source.attribution.sessionId = 'mutated';
  assert.equal(inbox.after(0).attribution.sessionId, 'session-1');
  inbox.add(fault(1, 1)); assert.equal(inbox.count(), 1);
  assert.equal(inbox.after(1), undefined);
  console.log('PASS T037 真实流程：延后独立故障、身份、原生日志确认、新 Surface、硬解名额与软件回退');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
