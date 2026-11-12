// 运行真实页面流程；首帧和系统录制均为替身。
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const file=path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/Index.ets');
const source=fs.readFileSync(file,'utf8');
let calls=[],recording=false;
global.XComponentController=class{};
const original=Module._load;
Module._load=function(name,parent,main){
 if(name==='./AudioCapture')return{AudioCapture:class{async start(){calls.push('capture-start');recording=true;}assertRecording(){assert(recording);}async finish(){calls.push('capture-finish');recording=false;}}};
 if(name==='./FocusAlarm')return{FocusAlarm:class{async start(){} async stop(){} samplesWritten(){return 48000;}}};
 if(name==='./FocusRun')return{runFocusProbe:async port=>{await port.confirmManualResume();await port.resume();}};
 if(name==='@kit.ArkUI')return{window:{getLastWindow:async()=>({setWindowKeepScreenOn:async()=>{},getWindowProperties:()=>({isKeepScreenOn:false})})}};
 if(name.startsWith('@kit.'))return{};
 if(name==='@vidall/player')return{getPlayerRuntimeStatus:()=>({state:'ready'}),createPlayer:()=>{throw Error('MUST_NOT_CREATE_AFTER_EXIT');}};
 return original.call(this,name,parent,main);
};
const stripped=source.slice(0,source.indexOf('  build() {')).replace('@Entry','').replace('@Component','').replace('struct Index','class Index').replace(/@State /g,'')+'}\nexports.Index=Index;';
const m=new Module(file,module);m.filename=file;m.paths=module.paths;
m._compile(ts.transpileModule(stripped,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file);
(async()=>{
 const p=new m.exports.Index();p.context={};p.root='/fake';p.ready=true;p.surface=true;
 p.run=async()=>{assert(recording);calls.push('playback');};
 p.record=()=>{};await p.startCaptured();assert.deepEqual(calls,['capture-start','playback','capture-finish']);
 calls=[];await p.startCaptured();assert.deepEqual(calls,[],'不允许重复录制复用状态');
 const q=new m.exports.Index();q.context={};q.root='/fake';q.ready=true;q.surface=true;q.record=()=>{};
 q.run=async()=>{throw Error('PLAYBACK_FAILED');};q.finish=async()=>calls.push('player-finish');
 await q.startCaptured();assert.match(q.status,/失败/);assert(calls.includes('capture-finish'));
 assert(source.includes(".id('audio-capture-start')"));
 const stopped=new m.exports.Index();stopped.record=()=>{};stopped.aboutToDisappear();
 await assert.rejects(stopped.open(1),/PROBE_CANCELLED/);
 const focus=new m.exports.Index();focus.record=()=>{};
 focus.delay=async()=>{assert.equal(focus.awaitingManualResume,true);focus.acceptManualResume();};
 let resumed=0;await focus.focusFlow({play:async()=>resumed++});assert.equal(resumed,1);
 assert(source.includes(".id('audio-focus-start')"));
 console.log('PASS: 录制开始后才播放、一次性启动、失败清理、退出禁止新会话、手动恢复');
})().catch(e=>{console.error(e);process.exitCode=1;});
