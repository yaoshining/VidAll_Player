// 执行真实 createPlayer / PlayerSession / bridge，替换的仅是平台 NAPI。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const creations = [];
let state = 'ready';
const native = {
  getRuntimeStatus: () => JSON.stringify({state}),
  createSession: async (...args) => { creations.push(args); return {ok:true,handle:creations.length,code:'OK'}; },
  setEventCallback: () => ({ok:true,handle:1,code:'OK'}),
  releaseSession: async () => ({ok:true,handle:1,code:'RELEASED'}),
};
const original = Module._load;
Module._load = function(name,parent,main) {
  if (name === 'libvidall_player_native.so') return {__esModule:true,default:native};
  if (name === '@kit.ArkTS') return {util:{}};
  return original.call(this,name,parent,main);
};
require.extensions['.ets'] = (module,file) => module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}
}).outputText,file);
const {createPlayer} = require('../../../packages/vidall-player/src/main/ets/public/player.ets');
(async () => {
  for (const options of [undefined, {hardwareDecoding:'disabled'}, {playbackMode:'compatible'},
      {playbackMode:'compatible',hardwareDecoding:'auto'}]) {
    const player = createPlayer(options);
    await player.release();
  }
  assert.deepEqual(creations.map(row => [row[1], row[4]]), [
    ['auto','standard'], ['no','standard'], ['no','compatible'], ['no','compatible'],
  ], '默认仍硬解优先；原 disabled 不改渲染；compatible 明确贯穿 PlayerSession 与 bridge');
  const count = creations.length;
  assert.throws(() => createPlayer({playbackMode:'misspelled'}), /INVALID_PLAYBACK_MODE/);
  assert.equal(creations.length,count,'非法模式不能创建原生会话');
  state = 'terminal';
  assert.throws(() => createPlayer({playbackMode:'compatible'}), /PLAYER_TERMINAL/,
    '兼容基础接口不能绕过尚未完成安全恢复的终局保护');
  console.log('PASS 兼容模式公开链路、默认兼容性、非法模式与终局保护');
})().catch(error => { console.error(error);process.exitCode=1; });
