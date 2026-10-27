// 与实际ArkTS入口共用的状态机；依赖替身只提供观察，不代替真实设备验收。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../normal-core/node_modules/typescript');
const file = path.resolve(__dirname, '../../../fixtures/device-smoke/entry/src/main/ets/smoke/SmokeSession.ets');
const source=fs.readFileSync(file,'utf8');
const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const box={exports:{},setTimeout,clearTimeout,Promise};vm.runInNewContext(result.outputText,box);const {SmokeSession}=box.exports;
class Port {
 constructor(fail=''){this.t=0;this.position=0;this.frames=0;this.errors=0;this.paused=false;this.active=false;this.completed=false;this.fail=fail;this.events=[];this.releases=0;this.opens=0;this.keep=[];}
 now(){return this.t;}
 async sleep(ms){this.t+=ms;if(this.active&&!this.paused&&this.fail!=='no-progress'){this.position=Math.min(30000,this.position+ms);this.completed=this.position>=30000;}}
 async initialize(){if(this.fail==='initialize')throw new Error('INIT_FAILED');if(this.fail==='hang')return new Promise(()=>{});}
 async open(cycle){this.opens++;this.position=0;this.completed=false;this.active=true;this.paused=false;if(this.fail!=='no-frame'&&!(this.fail==='reopen-frame'&&cycle===2))this.frames++;}
 async sample(){return {positionMs:this.position,durationMs:this.fail==='wrong-duration'?1000:30000,paused:this.paused,completed:this.completed&&this.fail!=='no-eof',frames:this.frames,errors:this.fail==='player-error'?1:0};}
 async pause(){if(this.fail!=='pause')this.paused=true;}
 async play(){if(this.fail!=='resume')this.paused=false;}
 async seek(percent){if(this.fail!=='seek')this.position=30000*percent/100;}
 async release(){this.releases++;this.active=false;if(this.fail==='release')throw new Error('RELEASE_FAILED');}
 async keepScreen(enabled){this.keep.push(enabled);return this.fail==='keep-false'&&!enabled?true:enabled;}
 record(event,cycle,value){if(this.fail==='journal')throw Error('DISK_FULL');this.events.push({event,cycle,value,elapsedMs:this.t});}
}
let count=0;
(async()=>{
 const p=new Port(),r=await new SmokeSession(p).run();assert.equal(r.passed,true);assert.equal(r.cleanupPassed,true);assert.equal(p.opens,2);assert.ok(p.releases>=2);assert.deepEqual(p.keep,[true,false]);
 for(const name of ['runtime-ready','frame','progress','paused','resumed','seek-request','seek-complete','closed','reopened','eof','release-complete','keep-screen','session-end'])assert.ok(p.events.some(x=>x.event===name),name);
 assert.ok(JSON.parse(p.events.find(e=>e.event==='paused').value).intervalMs>=1000);assert.equal(p.events.at(-1).event,'session-end');assert.equal(p.events.at(-1).value,'passed');count++;
 for(const mode of ['initialize','no-frame','no-progress','wrong-duration','pause','resume','seek','reopen-frame','no-eof','player-error','release','keep-false']){
  const p=new Port(mode),r=await new SmokeSession(p).run();assert.equal(r.passed,false,mode);assert.ok(p.keep.includes(false),mode+'保屏finally');assert.ok(!p.events.some(e=>e.event==='session-end'&&e.value==='passed'),mode+'不得假通过');assert.ok(p.events.some(e=>e.event==='session-failed'),mode);count++;
 }
 const p2=new Port('hang'),r2=await new SmokeSession(p2,25,25).run();assert.equal(r2.passed,false);assert.ok(p2.keep.includes(false));count++;
 const jp=new Port('journal'),jr=await new SmokeSession(jp).run();assert.equal(jr.passed,false);assert.ok(jp.keep.includes(false));count++;
 const staleFailures=[];
 async function staleCase(name,run){try{await run();count++;}catch(e){staleFailures.push({name,error:e.message});}}
 await staleCase('stale-once-recovers',async()=>{const p=new Port();const sample=p.sample.bind(p);let n=0;p.sample=async guard=>{guard?.();if(n++===0)throw Error('DIAGNOSTICS_STALE');return sample();};const r=await new SmokeSession(p).run();assert.equal(r.passed,true);assert.equal(p.events.at(-1).event,'session-end');assert.ok(n>1);});
 await staleCase('stale-50-attempt-bound',async()=>{const p=new Port();let n=0;p.sample=async()=>{n++;throw Error('DIAGNOSTICS_STALE');};const r=await new SmokeSession(p).run();assert.equal(r.passed,false);assert.equal(r.error,'DIAGNOSTICS_STALE');assert.equal(n,50);assert.ok(p.t<=5000);assert.ok(p.keep.includes(false));});
 await staleCase('stale-frozen-clock-count-bound',async()=>{const p=new Port();p.sleep=async()=>{};let n=0;p.sample=async()=>{n++;throw Error('DIAGNOSTICS_STALE');};const r=await new SmokeSession(p).run();assert.equal(r.error,'DIAGNOSTICS_STALE');assert.equal(n,50);});
 await staleCase('cancelled-stale-no-retry',async()=>{const p=new Port();const session=new SmokeSession(p);let n=0;p.sample=async()=>{n++;session.cancel();throw Error('DIAGNOSTICS_STALE');};const r=await session.run();assert.equal(r.error,'SESSION_CANCELLED');assert.equal(n,1);});
 await staleCase('deadline-stale-no-next-request',async()=>{const p=new Port();let n=0;p.sample=async()=>{n++;throw Error('DIAGNOSTICS_STALE');};const r=await new SmokeSession(p,50).run();assert.equal(r.error,'SESSION_TIMEOUT');assert.equal(n,1);});
 await staleCase('valid-result-after-cancel-rejected',async()=>{const p=new Port();const session=new SmokeSession(p);const original=p.sample.bind(p);p.sample=async()=>{session.cancel();return original();};await assert.rejects(()=>session.checked(),/SESSION_CANCELLED/);});
 for(const error of ['DIAGNOSTICS_RELEASED','PLAYER_TERMINAL','PRIVATE_OTHER_FAILURE'])await staleCase('no-retry-'+error,async()=>{const p=new Port();let n=0;p.sample=async()=>{n++;throw Error(error);};const r=await new SmokeSession(p).run();assert.equal(r.error,error);assert.equal(n,1);});
 await staleCase('late-retry-success-rejected',async()=>{const p=new Port();const original=p.sample.bind(p);let calls=0;p.sample=async()=>{if(++calls===1)throw Error('DIAGNOSTICS_STALE');p.t+=5001;return original();};const r=await new SmokeSession(p).run();assert.equal(r.passed,false);assert.equal(r.error,'DIAGNOSTICS_STALE');assert.equal(calls,2);});
if(staleFailures.length){console.error(JSON.stringify({staleFailures,casesAttempted:count+staleFailures.length}));throw Error('stale regression failed');}
 console.log(JSON.stringify(process.argv.includes('--trace-json')?{events:p.events,passed:true,scope:'actual SmokeSession with fake platform observations'}:{passed:true,cases:count,scope:'实际SmokeSession函数/模拟播放器观察；不是设备通过'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
