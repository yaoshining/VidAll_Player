const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const file=path.resolve(__dirname,'../../../fixtures/normal-core-consumer/raw-capture/RawCapture.ets');
let state=0,error=0,begin=0,end=0,closed=0,api=24;
const native={start:async()=>{begin++;return '{}';},status:()=>JSON.stringify({state,error}),finish:async()=>{end++;return JSON.stringify({state:2,error,records:12});}};
const original=Module._load;Module._load=function(n,p,m){if(n==='libraw_capture.so')return{default:native};if(n==='@kit.BasicServicesKit')return{deviceInfo:{get sdkApiVersion(){return api;}}};if(n==='@kit.CoreFileKit')return{fileIo:{OpenMode:{CREATE:1,READ_WRITE:2,TRUNC:4},openSync:()=>({fd:7}),closeSync:()=>closed++}};return original.call(this,n,p,m);};
const mod=new Module(file,module);mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,file);
const {RawCapture}=mod.exports;const make=()=>new RawCapture(()=>{},async()=>{});
(async()=>{
 let a=make();await a.start('/test');a.assertRecording();await Promise.all([a.finish(),a.finish()]);assert.equal(end,1);assert.equal(closed,1);await assert.rejects(a.start('/test'),/ONE_SHOT/);
 a=make();state=1;await assert.rejects(a.start('/test'),/STATE/);await a.finish();assert.equal(end,2);
 a=make();state=-1;await assert.rejects(a.start('/test'),/TIMEOUT/);await a.finish();
 a=make();state=0;error=42;await assert.rejects(a.start('/test'),/ERROR/);await assert.rejects(a.finish(),/ERROR/);assert.equal(closed,4);
 a=make();api=18;await assert.rejects(a.start('/test'),/API19/);await a.finish();assert.equal(end,4);
 console.log('PASS 原始采集启动、拒绝/超时、错误保留、一次性释放及API边界');
})().catch(e=>{console.error(e);process.exitCode=1;});
