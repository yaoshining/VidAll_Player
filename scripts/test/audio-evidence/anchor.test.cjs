const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
const file=path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/TimeAnchor.ets');
let write,now=100000,frame=0,events=[],painted=[],calls=[],api=24,stampError=false,releaseError=false;
const fake={on:(name,cb)=>{if(name==='writeData')write=cb;},start:async()=>calls.push('start'),stop:async()=>calls.push('stop'),release:async()=>{calls.push('release');if(releaseError)throw Error('release');},getAudioTimestampInfo:async()=>{assert(!calls.includes('in-callback'));if(stampError)throw Error('timestamp');return {framePos:frame,timestamp:now*1e6};}};
const original=Module._load;Module._load=function(name,p,m){if(name==='@kit.AudioKit')return{audio:{createAudioRenderer:async()=>fake,AudioSamplingRate:{SAMPLE_RATE_48000:48000},AudioChannel:{CHANNEL_2:2},AudioSampleFormat:{SAMPLE_FORMAT_S16LE:1},AudioEncodingType:{ENCODING_TYPE_RAW:0},StreamUsage:{STREAM_USAGE_MUSIC:1}}};if(name==='@kit.BasicServicesKit')return{systemDateTime:{TimeType:{ACTIVE:1},getUptime:()=>now*1e6},deviceInfo:{get sdkApiVersion(){return api;}}};return original.call(this,name,p,m);};
const mod=new Module(file,module);mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file);
const {TimeAnchor,anchorCode,fillAnchorPcm}=mod.exports;
function make(){events=[];calls=[];frame=0;now=100000;stampError=false;releaseError=false;return new TimeAnchor((e,v)=>events.push([e,JSON.parse(v)]),bits=>painted.push(bits),async ms=>{now+=ms;const b=new ArrayBuffer(ms*48*4);write(b);frame+=ms*48;});}
(async()=>{
 for(const n of [0,1,2048,4095]){const b=anchorCode(n);assert.equal(b.length,16);assert.deepEqual(b.slice(0,3),[1,1,0]);assert.equal(b.slice(3,15).reduce((s,v)=>s*2+v,0),n);assert.equal(b.reduce((s,v)=>s^v,0),0);}
 for(const n of [-1,4096,NaN,1.5])assert.throws(()=>anchorCode(n),/ANCHOR_SEQUENCE/);
 const silent=new Int16Array(960);assert.equal(fillAnchorPcm(silent,0,true),480);assert(silent.every(v=>v===0));const pulse=new Int16Array(960);fillAnchorPcm(pulse,48000,true);assert(pulse.some(v=>v!==0));for(let i=0;i<pulse.length;i+=2)assert.equal(pulse[i],pulse[i+1]);fillAnchorPcm(pulse,48000,false);assert(pulse.every(v=>v===0));
 let a=make();await a.calibrate('before');assert.equal(events.filter(x=>x[0]==='anchor-audio-timestamp').length,12);assert.deepEqual(calls,['start','stop','release']);assert.equal(events.find(x=>x[0]==='anchor-audio-plan')[1].frequencyHz,2200);
 a=make();stampError=true;await assert.rejects(a.calibrate('before'),/timestamp/);assert.deepEqual(calls,['start','stop','release']);
 a=make();releaseError=true;await assert.rejects(a.calibrate('before'),/release/);await assert.rejects(a.calibrate('after'),/ANCHOR_RENDERER_RETAINED/);assert.equal(calls.filter(x=>x==='release').length,1);
 a=make();api=18;await assert.rejects(a.calibrate('before'),/ANCHOR_API19_REQUIRED/);assert.equal(calls.length,0);api=24;
 a=make();await a.close();await assert.rejects(a.calibrate('before'),/ANCHOR_CLOSED/);
 a=make();let resolveQuery;const savedQuery=fake.getAudioTimestampInfo;fake.getAudioTimestampInfo=()=>new Promise(resolve=>{resolveQuery=resolve;});
 await assert.rejects(a.calibrate('before'),/ANCHOR_TIMESTAMP_TIMEOUT/);assert.deepEqual(calls,['start']);
 await assert.rejects(a.close(),/ANCHOR_QUERY_PENDING_RETAINED/);const silenceAfterTimeout=new ArrayBuffer(1920);write(silenceAfterTimeout);assert(new Int16Array(silenceAfterTimeout).every(v=>v===0));
 resolveQuery({framePos:48000,timestamp:now*1e6});await Promise.resolve();fake.getAudioTimestampInfo=savedQuery;
 a=make();const savedInterval=global.setInterval,savedClear=global.clearInterval;let tick,cleared=false;global.setInterval=cb=>{tick=cb;return 99;};global.clearInterval=()=>{cleared=true;};
 a.startVisual();now+=200;tick();assert.equal(events.filter(x=>x[0]==='anchor-visual').length,2);assert.equal(painted.at(-1).length,16);await a.close();assert(cleared);global.setInterval=savedInterval;global.clearInterval=savedClear;

 console.log('PASS: 时间码、PCM边界、独立时间戳、查询失败、释放保留、旧API及取消');
})().catch(e=>{console.error(e);process.exitCode=1;});
