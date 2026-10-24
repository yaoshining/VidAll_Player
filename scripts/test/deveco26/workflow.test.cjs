// 使用已锁定YAML解析器检查每个步骤，全文token不能证明失败证据路径。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const YAML=require('../normal-core/node_modules/yaml');
const root=path.resolve(__dirname,'../../..');
function verify(text){
 try{
 const doc=YAML.parse(text),jobs=doc.jobs,job=jobs.evaluation;
 assert.deepEqual(Object.keys(jobs),['evaluation']);
 assert.deepEqual(doc.on,{push:{branches:['codex/deveco26-evaluation']}});
 assert.equal(job['runs-on'],'macos-26');assert.equal(doc.permissions.contents,'read');
 const steps=job.steps,ids=Object.fromEntries(steps.filter(x=>x.id).map(x=>[x.id,x]));
 for(const id of ['context','contracts','bootstrap','runtime','target','cleanup','public_gate','upload','assess'])assert.ok(ids[id]);
 for(const id of ['cleanup','public_gate','assess'])assert.equal(ids[id].if,'always()');
 assert.equal(ids.upload.if,"always() && steps.public_gate.outcome == 'success'");
 assert.equal(ids.upload.uses,'actions/upload-artifact@v4');assert.equal(ids.upload.with['if-no-files-found'],'error');
 assert.match(ids.context.run,/ci-context\.py/);assert.match(ids.target.run,/evaluate\.py build/);assert.match(ids.public_gate.run,/evaluate\.py finish/);assert.match(ids.assess.run,/evaluate\.py assess/);assert.match(ids.cleanup.run,/bootstrap\.py cleanup/);
 assert.match(ids.runtime.run,/runtime\.test\.py/);assert.match(ids.runtime.run,/export DEVECO26_SDK=/);assert.match(ids.runtime.run,/export DEVECO26_CMAKE=/);
 assert.ok(steps.indexOf(ids.bootstrap)<steps.indexOf(ids.runtime));assert.ok(steps.indexOf(ids.runtime)<steps.indexOf(ids.target));
 assert.equal(ids.bootstrap.env.DEVECO26_ARCHIVE_URL,'${{ secrets.DEVECO26_ARCHIVE_URL }}');
 for(const step of steps)if(step!==ids.bootstrap)assert.ok(!JSON.stringify(step).includes('secrets.'));
 const checkout=steps.find(x=>x.uses==='actions/checkout@v4');assert.equal(checkout.with['persist-credentials'],false);assert.ok(!checkout.with.ref);
 return true;
 }catch{return false;}
}
const original=fs.readFileSync(path.join(root,'.github/workflows/deveco26-evaluation.yml'),'utf8');
assert.ok(verify(original),'当前独立工作流不满足门禁');
let rejected=0;
for(const id of ['cleanup','public_gate','upload','assess']){
 const doc=YAML.parse(original);doc.jobs.evaluation.steps.find(x=>x.id===id).if='success()';assert.equal(verify(YAML.stringify(doc)),false,`${id}失败路径变异被接受`);rejected++;
}
for(const id of ['context','contracts','bootstrap','runtime','target','cleanup','public_gate','upload','assess']){
 const doc=YAML.parse(original);doc.jobs.evaluation.steps=doc.jobs.evaluation.steps.filter(x=>x.id!==id);assert.equal(verify(YAML.stringify(doc)),false);rejected++;
}
console.log(JSON.stringify({passed:true,structuralChecks:true,mutantsRejected:rejected}));
