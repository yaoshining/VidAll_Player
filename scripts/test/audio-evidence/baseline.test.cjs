const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const file=path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/SystemBaseline.ets');
let calls=[],failPrepare=false,failRelease=false,cancelled=false;
const player={state:'idle',on(){},set url(v){throw Error('FILE_URL_UNSUPPORTED');},set fdSrc(v){assert.equal(v.fd,31);assert.equal(v.offset,0);assert.equal(v.length,180);calls.push('fd');this.state='initialized';},set surfaceId(v){calls.push('surface');},
 async prepare(){calls.push('prepare');if(failPrepare)throw Error('PREPARE_FAILED');this.state='prepared';},
 async play(){calls.push('play');this.state='playing';},async release(){calls.push('release');if(failRelease)throw Error('RELEASE_FAILED');this.state='released';}};
const original=Module._load;Module._load=function(n,p,m){if(n==='@kit.CoreFileKit')return{fileIo:{OpenMode:{READ_ONLY:0},openSync(){calls.push('open');return{fd:31};},statSync(){return{size:180};},closeSync(fd){assert.equal(fd.fd,31);calls.push('close');}}};if(n==='@kit.MediaKit')return{media:{createAVPlayer:async()=>{calls.push('create');player.state='idle';return player;}}};return original.call(this,n,p,m);};
const mod=new Module(file,module);mod.filename=file;mod.paths=module.paths;
mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file);
const make=()=>new mod.exports.SystemBaseline(()=>{},async()=>{if(cancelled)throw Error('CANCELLED');});
(async()=>{
 await make().run('/own/test.mp4','surface');assert.deepEqual(calls,['create','open','fd','surface','prepare','play','release','close']);
 calls=[];failPrepare=true;await assert.rejects(make().run('/own/test.mp4','surface'),/PREPARE_FAILED/);assert.equal(calls.at(-1),'close');failPrepare=false;
 calls=[];cancelled=true;await assert.rejects(make().run('/own/test.mp4','surface'),/CANCELLED/);assert.equal(calls.at(-1),'close');cancelled=false;
 calls=[];const b=make();failRelease=true;await assert.rejects(b.run('/own/test.mp4','surface'),/RELEASE_FAILED/);await assert.rejects(b.close(),/RELEASE_FAILED/);assert.equal(calls.filter(x=>x==='release').length,1);assert(!calls.includes('close'),'释放未确认时保留文件');failRelease=false;
 calls=[];await assert.rejects(make().run('/own/test.mp4',''),/BASELINE_SURFACE_MISSING/);assert.deepEqual(calls,[]);
 console.log('PASS: 系统对照正常、初始化失败、取消、释放失败与空surface');
})().catch(e=>{console.error(e);process.exitCode=1;});
