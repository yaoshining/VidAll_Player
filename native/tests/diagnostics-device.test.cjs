const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
require.extensions['.ets'] = (m,f) => m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const { validateProbeSnapshot, summarizeTimings } = require('../../entry/src/main/ets/player/DiagnosticsProbeChecks.ets');
assert.deepEqual(summarizeTimings([]), {count:0,medianMs:0,p95Ms:0,maxMs:0});
assert.deepEqual(summarizeTimings([1,3,2,10]), {count:4,medianMs:2.5,p95Ms:10,maxMs:10});
assert.equal(validateProbeSnapshot({schemaVersion:1,fields:{}},640,360).length > 0,true);
const s={schemaVersion:1,fields:{videoInputWidth:{status:'available',value:640},videoInputHeight:{status:'available',value:360},filename:{status:'unavailable'},mediaTitle:{status:'unavailable'}}};
assert.deepEqual(validateProbeSnapshot(s,640,360),[]);
s.fields.videoInputWidth.value=1920;assert.equal(validateProbeSnapshot(s,640,360).length,1);
assert.equal(summarizeTimings([1,3,2,10]).medianMs,2.5);
assert.equal(summarizeTimings([3,1,2]).medianMs,2);
s.fields.videoInputWidth={status:'unavailable',value:640};
assert.ok(validateProbeSnapshot(s,640,360).includes('videoInputWidth'));
const { validateLiveSnapshot, validateSurfaceRebuild } = require('../../entry/src/main/ets/player/DiagnosticsProbeChecks.ets');
const live={fields:{durationMs:{status:'available',estimated:true},progressPercent:{status:'available',estimated:true},fileSizeBytes:{status:'unavailable'}}};
assert.deepEqual(validateLiveSnapshot(live),[]);
for(const key of ['durationMs','progressPercent','fileSizeBytes']) {
 const bad=structuredClone(live);bad.fields[key].status='error';assert.ok(validateLiveSnapshot(bad).length);
}
for(const key of ['durationMs','progressPercent']) {
 const bad=structuredClone(live);bad.fields[key].estimated=false;assert.ok(validateLiveSnapshot(bad).length);
 const absent=structuredClone(live);absent.fields[key]={status:'unavailable'};assert.deepEqual(validateLiveSnapshot(absent),[]);
}
const surface={destroyed:true,loaded:true,attached:true,firstFrame:true,oldId:'old',newId:'new',generation:2};
assert.equal(validateSurfaceRebuild(surface),true);
for(const key of ['destroyed','loaded','attached','firstFrame']) assert.equal(validateSurfaceRebuild({...surface,[key]:false}),false);
assert.equal(validateSurfaceRebuild({...surface,newId:'old'}),false);
assert.equal(validateSurfaceRebuild({...surface,generation:1}),false);

for (const key of ['videoInputWidth','videoInputHeight']) {
 for (const status of ['unavailable','unsupported','error']) {
  const stale=structuredClone(s);stale.fields.videoInputWidth={status:'available',value:640};
  stale.fields[key].status=status;assert.ok(validateProbeSnapshot(stale,640,360).includes(key));
 }
}
for (const key of ['durationMs','progressPercent','fileSizeBytes']) {
 const bad=structuredClone(live);bad.fields[key].status='unsupported';assert.ok(validateLiveSnapshot(bad).length);
}
console.log('真机探针断言测试通过');
