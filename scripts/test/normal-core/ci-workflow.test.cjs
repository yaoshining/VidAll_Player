// 解析实际 workflow，不用文本存在替代事件/job语义。
const fs=require('fs'),path=require('path'),assert=require('assert');
const yaml=require('./node_modules/yaml');
const file=process.argv[2]||path.resolve(__dirname,'../../../.github/workflows/normal-core.yml');
const w=yaml.parse(fs.readFileSync(file,'utf8'));const results=[];
function check(name,fn){try{fn();results.push({name,passed:true})}catch(e){results.push({name,passed:false,error:e.message})}}
check('pr-main',()=>{assert(w.on.pull_request);assert(w.on.pull_request.branches.includes('main'));assert(!w.on.pull_request.paths)});
check('push-main-head',()=>{for(const b of ['main','codex/004-normal-core-integration','codex/docs-pr4-speckit-closeout'])assert(w.on.push.branches.includes(b))});
check('merge-group',()=>assert(w.on.merge_group.types.includes('checks_requested')));
check('manual',()=>assert(Object.hasOwn(w.on,'workflow_dispatch')));
check('checkout-event-sha',()=>{for(const id of ['host-contracts','target-har']){const step=w.jobs[id].steps.find(s=>s.uses?.startsWith('actions/checkout@'));assert(step);assert(!step.with?.ref||step.with.ref==='${{ github.sha }}');assert.equal(step.with?.['fetch-depth'],0)}});
check('real-host-and-context',()=>{const s=w.jobs['host-contracts'].steps;assert(s.some(x=>x.run?.includes('ci-context.py')));assert(s.some(x=>x.run?.includes('normal-core/run.py')));assert(s.some(x=>x.run?.includes('ci-contract.test.py')));assert(s.some(x=>x.run?.includes('ci-schema.py')))});
check('real-target-no-signing',()=>{const j=w.jobs['target-har'];assert(j['runs-on'].includes('self-hosted'));assert(j.steps.some(x=>x.run?.includes('ci-target.py')));assert(!JSON.stringify(j).match(/check_signing|signing_ready|\.p12|\.p7b/));assert(j.if.includes('head.repo.full_name'))});
check('failure-evidence',()=>{for(const id of ['host-contracts','target-har']){const s=w.jobs[id].steps;assert(s.some(x=>x.id==='public_gate'&&x.if==='always()'&&x.run?.includes('ci-evidence.py finish')));assert(s.some(x=>x.uses?.startsWith('actions/upload-artifact@')&&x.if?.includes('always()')&&x.if?.includes('success')))}});
check('aggregate-not-skip-success',()=>{const j=w.jobs['normal-core-result'];assert.equal(j.if,'always()');assert.deepEqual([...j.needs].sort(),['host-contracts','target-har']);assert(j.steps.some(x=>x.run?.includes('ci-evidence.py verdict')))});
check('failure-cannot-be-ignored',()=>{for(const id of ['host-contracts','target-har']){const j=w.jobs[id];assert(!j['continue-on-error']);assert(j.steps.every(s=>!s['continue-on-error']));assert(j.steps.some(s=>s.if==='always()'&&s.run?.includes('ci-evidence.py assess')))}});
console.log(JSON.stringify({passed:results.every(r=>r.passed),results},null,2));process.exitCode=results.some(r=>!r.passed)?1:0;
