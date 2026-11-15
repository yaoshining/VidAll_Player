// 执行独立验收工具的真实代码；平台订阅、文件与保存选择器使用替身。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let watcher, removed = 0, reads = 0, copies = 0, closed = [], destinations = ['file://chosen'], failure = '', files = new Map(), readGate;
const api = {
  OpenMode: { READ_ONLY: 1, READ_WRITE: 2, CREATE: 4, TRUNC: 8 },
  async readText(p, options) { reads++; assert(options.length <= 524288); if (readGate) await readGate; if (failure === 'read') throw Error('READ_FAIL'); return 'stack'; },
  async open(p) { if (failure === 'open') throw Error('OPEN_FAIL'); return { fd: p }; },
  async write(fd, value) { if (failure === 'write') throw Error('WRITE_FAIL'); files.set(fd, value); },
  async close(f) { closed.push(f.fd); },
  async copyFile(src, dest) { copies++; if (failure === 'copy') throw Error('COPY_FAIL'); },
  async stat() { return { size: 600000 }; }
};
const original = Module._load;
Module._load = function(name, parent, main) {
  if (name === '@kit.PerformanceAnalysisKit') return { hiAppEvent: { event: { APP_CRASH: 'APP_CRASH' }, addWatcher(w) { watcher = w; return {}; }, removeWatcher(w) { assert.equal(w, watcher); removed++; } } };
  if (name === '@kit.CoreFileKit') return { fileIo: api, picker: { DocumentViewPicker: class { async save() { if (failure === 'picker') throw Error('PICKER_FAIL'); return destinations; } } } };
  if (name === '@kit.AbilityKit') return {};
  return original.call(this, name, parent, main);
};
const file = path.resolve(__dirname, '../../../fixtures/normal-core-consumer/audio-evidence/EvidenceFiles.ets');
const m = new Module(file, module); m.filename = file; m.paths = module.paths;
m._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, file);
const { EvidenceFiles } = m.exports;
const event = (params = {}) => [{ appEventInfos: [{ name: 'APP_CRASH', params: { bundle_name: 'com.yaoshining.vidallplayer', external_log: ['/data/storage/el2/log/hiappevent/APP_CRASH_1.log'], ...params } }] }];
(async () => {
  let notices = []; const e = new EvidenceFiles({}, '/root', s => notices.push(s)); e.start(); e.start();
  await e.receive('other', event()); await e.receive('OS', event({ bundle_name: 'other' }));
  await e.receive('OS', event({ external_log: ['/data/log/faultlogger/private'] }));
  await e.receive('OS', event({ external_log: ['/data/storage/el2/log/hiappevent/../private'] }));
  assert.equal(reads, 0);
  await e.receive('OS', event()); assert.equal(reads, 1); assert.match(files.get('/root/crash.txt'), /stack/); assert.match(files.get('/root/crash.txt'), /截断/);
  await e.receive('OS', event()); assert.equal(reads, 1, '重复事件不重复读');
  for (let i = 2; i <= 6; i++) await e.receive('OS', event({ external_log: [`/data/storage/el2/log/hiappevent/APP_CRASH_${i}.log`] }));
  assert.equal(reads, 4, '单次运行最多四份');
  e.close(); e.close(); assert.equal(removed, 1); await e.receive('OS', event()); assert.equal(reads, 4);
  const late = new EvidenceFiles({}, '/late', s => notices.push(s)); late.start();
  let release; readGate = new Promise(r => release = r); const pending = late.receive('OS', event()); late.close(); release(); await pending; readGate = undefined;
  assert(!files.has('/late/crash.txt'), '离页后不得写入或更新UI');
  const bad = new EvidenceFiles({}, '/bad', s => notices.push(s)); bad.start(); failure = 'read'; await bad.receive('OS', event()); assert(notices.some(s => s.includes('READ_FAIL'))); failure = '';
  const x = new EvidenceFiles({}, '/root', () => {});
  await assert.rejects(x.exportFile('capture', true), /CAPTURE_BUSY/); assert.equal(copies, 0);
  destinations = []; assert.equal(await x.exportFile('capture', false), false); assert.equal(copies, 0);
  destinations = ['file://chosen']; assert.equal(await x.exportFile('capture', false), true); assert(closed.includes('file://chosen')); assert(closed.includes('/root/capture.mp4'));
  failure = 'copy'; const n = closed.length; await assert.rejects(x.exportFile('events', false), /COPY_FAIL/); assert.equal(closed.length, n + 2);
  failure = 'picker'; await assert.rejects(x.exportFile('crash', false), /PICKER_FAIL/); failure = '';
  let unlock; const oldCopy = api.copyFile; api.copyFile = async () => new Promise(r => unlock = r);
  const exporting = x.exportFile('events', false); while (!unlock) await Promise.resolve();
  await assert.rejects(x.exportFile('events', false), /EXPORT_BUSY/); unlock(); await exporting; api.copyFile = oldCopy;
  console.log('PASS: 本应用崩溃过滤、有界读取、重复/迟到事件、导出取消/失败/并发与句柄清理');
})().catch(e => { console.error(e); process.exitCode = 1; });
