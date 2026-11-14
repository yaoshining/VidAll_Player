const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const file=path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/SeekRun.ets');
const m=new Module(file,module);m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file);
async function run(positions,flags={}){let n=0,waited=0,events=[];await m.exports.verifySeekProgress({snapshot:async()=>({positionMs:positions[Math.min(n++,positions.length-1)],paused:false,buffering:false,...flags}),delay:async ms=>{waited+=ms;},record:(e,v)=>events.push([e,v])},120000);return{waited,events};}
(async()=>{
 // 与本轮实际关键帧落点一致：临时目标120s先回落119.03s，再正常推进。
 assert.equal((await run([120000,119033,119166,119766])).waited,1000);
 assert.equal((await run([120000,120133,120733])).waited,850);
 await assert.rejects(run(Array(30).fill(120000)),/SEEK_NOT_ADVANCING/);
 await assert.rejects(run([119000,119100,119200]),/SEEK_NOT_ADVANCING/);
 await assert.rejects(run([95000,95100,95700]),/SEEK_TARGET_MISMATCH/);
 await assert.rejects(run([120000,120100,120700],{paused:true}),/SEEK_NOT_ADVANCING/);
 await assert.rejects(run([120000,120100,120700],{buffering:true}),/SEEK_NOT_ADVANCING/);
 await assert.rejects(run([NaN]),/SEEK_DIAGNOSTIC_INVALID/);
 console.log('PASS: 临时目标回落、正常推进、永久停滞、目标错误、暂停、缓冲及非法诊断');
})().catch(e=>{console.error(e);process.exitCode=1;});
