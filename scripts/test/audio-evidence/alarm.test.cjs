const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH||'/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let writes,calls,renderer,completeCreate;
const original=Module._load;
Module._load=function(n,p,m){if(n==='@kit.AudioKit')return{audio:{AudioSamplingRate:{SAMPLE_RATE_48000:48000},AudioChannel:{CHANNEL_2:2},AudioSampleFormat:{SAMPLE_FORMAT_S16LE:1},AudioEncodingType:{ENCODING_TYPE_RAW:0},StreamUsage:{STREAM_USAGE_ALARM:4},InterruptMode:{INDEPENDENT_MODE:1},createAudioRenderer:async opts=>{assert.equal(opts.rendererInfo.usage,4);calls.push('create');if(completeCreate)await new Promise(r=>completeCreate=r);return renderer;}}};return original.call(this,n,p,m);};
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {FocusAlarm}=require(path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/FocusAlarm.ets'));
function setup(overrides={}){calls=[];completeCreate=undefined;renderer={on:(name,cb)=>{if(name==='writeData')writes=cb;},setInterruptMode:async mode=>{assert.equal(mode,1);calls.push('independent');},start:async()=>{calls.push('start');},stop:async()=>calls.push('stop'),release:async()=>calls.push('release'),...overrides};return new FocusAlarm(()=>{});}
(async()=>{
 let a=setup();await a.start();const buffer=new ArrayBuffer(48000*4);writes(buffer);assert.equal(a.samplesWritten(),48000);const pcm=new Int16Array(buffer);assert(pcm.some(x=>x!==0));for(let i=0;i<pcm.length;i+=2)assert.equal(pcm[i],pcm[i+1]);await a.stop();await a.stop();assert.equal(calls.filter(x=>x==='release').length,1);assert.deepEqual(calls,['create','independent','start','stop','release']);writes(buffer);assert(pcm.every(x=>x===0));await assert.rejects(a.start(),/ONE_SHOT/);
 a=setup({start:async()=>{throw Error('START_FAILED');}});await assert.rejects(a.start(),/START_FAILED/);await a.stop();assert(calls.includes('release'));
 a=setup({stop:async()=>{throw Error('STOP_FAILED');}});await a.start();await assert.rejects(a.stop(),/STOP_FAILED/);assert(calls.includes('release'));
 a=setup();completeCreate=true;const starting=a.start();const rejected=assert.rejects(starting,/CANCELLED/);await new Promise(r=>setImmediate(r));const stopping=a.stop();assert(!calls.includes('release'));completeCreate();await rejected;await stopping;assert(!calls.includes('start'));assert(calls.includes('release'));
 console.log('PASS: Alarm真实适配器4组生命周期/迟到回调回归（系统为替身）');
})().catch(e=>{console.error(e);process.exitCode=1;});
