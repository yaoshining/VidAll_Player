// 执行诊断页的真实方法；仅移除 ArkUI 的声明式 build，平台库以替身提供。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const fixture = path.resolve(__dirname, '../../../fixtures/normal-core-consumer/recovery-fence');
const source = fs.readFileSync(path.join(fixture, 'Index.ets'), 'utf8');
assert.match(source, /runFenceProbe\(port\)/, '页面必须执行已回归的流程');
assert.equal((source.match(/XComponent\(\{/g) || []).length, 4, '保留四个独立 Surface');
assert.match(source, /late-close completed real=0/, '人工确认要写清原生日志条件');
assert.equal((source.match(/\.defaultFocus\(true\)/g) || []).length, 3, '三个互斥操作按钮都可用 TV 默认焦点操作');
let nativeFault, unsubscribes = 0, subscriptions = 0, intervalCalls = 0, pulse, pendingRelease, intervalCleared = false;
let surfaceId = 0;
global.XComponentController = class { constructor() { this.id = 'surface-' + ++surfaceId; } getXComponentSurfaceId() { return this.id; } };
const opened = [], writes = [];
const api = {
  initializePlayerRuntime: async (_context, options) => assert.equal(options.terminalPolicy, 'preserve-host'),
  getPlayerRuntimeStatus: () => ({ state: 'ready' }),
  onPlayerFault: callback => { subscriptions++; nativeFault = callback; return () => { unsubscribes++; }; },
  createPlayer: options => {
    const index = opened.length + 1;
    const player = {
      options, attachSurface: async value => { player.surface = value; },
      load: async (value, identity) => {
        player.source = value;
        identity({ sessionId: 'session-' + index, loadGeneration: '1' });
        options.eventListener({ type: 'state', state: 'playing' });
        options.eventListener({ type: 'firstFrame', surfaceGeneration: index });
      },
      play: async () => assert.fail('已经播放不应重复 play'),
      release: () => new Promise(resolve => { pendingRelease = resolve; }),
      getDiagnostics: async () => ({})
    };
    opened.push(player); return player;
  }
};
const kitFs = {
  OpenMode: { CREATE: 1, READ_WRITE: 2, APPEND: 4, TRUNC: 8 }, accessSync: () => true,
  open: async () => ({ fd: 1 }), write: async () => {}, close: async () => {},
  openSync: () => ({ fd: 1 }), writeSync: (_fd, text) => writes.push(JSON.parse(text)), closeSync: () => {}
};
const load = Module._load;
Module._load = function (name, parent, main) {
  if (name === '@vidall/player') return api;
  if (name === '@kit.AbilityKit') return {};
  if (name === '@kit.CoreFileKit') return { fileIo: kitFs };
  if (name === '@kit.ArkUI') return { window: { getLastWindow: async () => ({ setWindowKeepScreenOn: async () => {}, getWindowProperties: () => ({ isKeepScreenOn: false }) }) } };
  if (name === './ProbeChecks' && parent.filename.startsWith(fixture)) return load.call(this, path.join(fixture, '../recovery-terminal/ProbeChecks.ets'), parent, main);
  return load.call(this, name, parent, main);
};
require.extensions['.ets'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText, file);
const transformed = source.slice(0, source.indexOf('  build()'))
  .replace('@Entry', '').replace('@Component', '').replace(/@State /g, '').replace('struct Index', 'export class Index') + '}';
const pageModule = new Module(path.join(fixture, 'Index.ets'), module);
pageModule.filename = path.join(fixture, 'Index.ets');
pageModule.paths = module.paths;
pageModule._compile(ts.transpileModule(transformed, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, pageModule.filename);
const { Index } = pageModule.exports;

async function main() {
  const oldInterval = global.setInterval, oldClear = global.clearInterval, oldInfo = console.info;
  global.setInterval = fn => { intervalCalls++; pulse = fn; return 123; };
  global.clearInterval = id => { assert.equal(id, 123); intervalCleared = true; };
  console.info = () => {};
  try {
    const race = new Index(); const createdBeforeRace=opened.length;
    race.surfaceReady=[true,true,true,true];race.listVisible=true;
    race.delay=async()=>{race.acceptNext();race.cancelled=true;};
    await assert.rejects(race.openSession(2),/PROBE_CANCELLED/);
    assert.equal(opened.length,createdBeforeRace,'等待结束与离页交错后不得创建播放器');
    const page = new Index();
    page.getUIContext = () => ({ getHostContext: () => ({ filesDir: '/probe', resourceManager: { getRawFileContent: async () => new Uint8Array([1, 2]) } }) });
    await page.prepare();
    page.surfaceReady = [true, true, true, true];
    const first = await page.openSession(1);
    assert.equal(opened[0].options.playbackMode, 'standard');
    assert.equal(opened[0].surface.componentId, first.surfaceId);
    assert.match(opened[0].source.uri, /global-probe\.mp4$/);
    assert.deepEqual(first.identity, { sessionId: 'session-1', loadGeneration: '1' });
    const closing = page.closeSession(first);
    assert.equal(unsubscribes, 0, 'release 中不得断开独立 runtime 监听');
    nativeFault({ sequence: 1, kind: 'session-quarantined', platformError: -4, stage: 1,
      attribution: { state: 'known', sessionId: 'session-1', loadGeneration: '1' } });
    pulse(); pulse(); pulse(); pendingRelease(); await closing;
    assert.equal((await page.nextFault(0)).attribution.sessionId, 'session-1');
    assert(writes.some(value => value.event === 'release-heartbeat' && JSON.parse(value.value).ticks === 3));
    assert.equal(unsubscribes, 0);
    page.delay = async () => {
      if (page.awaitingReturn) assert.equal(page.onBackPress(), true);
      else if (page.listVisible) page.acceptNext();
    };
    await page.returnToList(first);
    assert(page.listVisible);
    const second = await page.openSession(2);
    assert.equal(opened[1].options.playbackMode, 'standard');
    assert.notEqual(first.surfaceId, second.surfaceId);
    assert.match(opened[1].source.uri, /test_video\.mp4$/);
    page.acceptLateClose(); assert.equal(page.lateCloseConfirmed, false, '不在确认阶段不能提前确认');
    page.delay = async () => { if (page.awaitingLateClose) page.acceptLateClose(); };
    await page.confirmLateClose();
    assert(writes.some(value => value.event === 'operator-native-log-confirmed'));
    page.aboutToDisappear();
    assert.equal(unsubscribes, 1);
    assert(intervalCleared);
    await assert.rejects(page.nextFault(1), /PROBE_CANCELLED/);
    const flowPage = () => {
      const p = new Index(), recorded = [];
      p.record = event => recorded.push(event);
      p.openSession = async index => ({ index, surfaceId: 'surface-' + index, identity: { sessionId: 'session-' + index, loadGeneration: '1' } });
      p.snapshot = async session => ({ schemaVersion: 1, freshness: 'live', fields: {
        renderBackend: { status: 'available', estimated: false, value: 'vulkan', source: 'session.actual-render-backend' },
        hardwareDecoder: { status: 'available', estimated: false, value: session.index === 4 ? 'no' : 'ohcodec', source: 'hwdec-current' }
      } });
      p.confirmPlayback = p.returnToList = p.confirmLateClose = async () => {};
      p.closeSession = async session => {
        if (session.index === 1 || session.index === 3) p.inbox.add({ sequence: session.index === 1 ? 1 : 2,
          kind: 'session-quarantined', stage: 1, platformError: -4,
          attribution: { state: 'known', sessionId: session.identity.sessionId, loadGeneration: session.identity.loadGeneration } });
      };
      return { p, recorded };
    };
    const failedCleanup = flowPage();
    failedCleanup.p.finish = async () => { throw new Error('KEEP_SCREEN_NOT_RELEASED'); };
    await assert.rejects(failedCleanup.p.run(), /KEEP_SCREEN_NOT_RELEASED/);
    assert(!failedCleanup.recorded.includes('summary'), '清理失败不得输出成功总结');
    const passed = flowPage(); passed.p.finish = async () => passed.recorded.push('cleanup-completed');
    await passed.p.run();
    assert(passed.recorded.indexOf('summary') > passed.recorded.indexOf('cleanup-completed'));
    const subscribeBefore = subscriptions, intervalBefore = intervalCalls;
    let initialized;
    api.initializePlayerRuntime = async () => new Promise(resolve => { initialized = resolve; });
    const leaving = new Index(); leaving.getUIContext = page.getUIContext;
    const preparing = leaving.prepare();
    await new Promise(resolve => setImmediate(resolve));
    assert(initialized, '准备流程应停在运行时初始化');
    leaving.aboutToDisappear(); initialized(); await preparing;
    assert.equal(subscriptions, subscribeBefore, '页面离开后不得迟到注册 runtime 监听');
    assert.equal(intervalCalls, intervalBefore, '页面离开后不得迟到创建心跳');
    console.info = oldInfo;
    console.log('PASS T037 页面绑定：standard、独立 Surface、release 中 runtime 故障、UI 心跳与人工确认');
  } finally {
    console.info = oldInfo; global.setInterval = oldInterval; global.clearInterval = oldClear;
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
