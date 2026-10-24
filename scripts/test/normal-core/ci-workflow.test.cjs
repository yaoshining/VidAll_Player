// 历史旧SDK目标已退役；保留手动云端宿主诊断，不冒充新默认构建通过。
const fs=require('fs'),path=require('path'),assert=require('assert'),yaml=require('./node_modules/yaml');
const file=process.argv[2]||path.resolve(__dirname,'../../../.github/workflows/normal-core.yml');
const w=yaml.parse(fs.readFileSync(file,'utf8'));const results=[];
function check(name,fn){try{fn();results.push({name,passed:true})}catch(e){results.push({name,passed:false,error:e.message})}}
check('manual-only',()=>assert.deepEqual(Object.keys(w.on),['workflow_dispatch']));
check('only-host',()=>assert.deepEqual(Object.keys(w.jobs),['host-contracts']));
const h=w.jobs['host-contracts'];
check('cloud-host',()=>assert.equal(h['runs-on'],'ubuntu-24.04'));
check('event-checkout',()=>{const s=h.steps.find(s=>s.uses?.startsWith('actions/checkout@'));assert(s);assert(!s.with?.ref);assert.equal(s.with?.['fetch-depth'],0)});
check('preserved-host-contracts',()=>{for(const token of ['ci-context.py','normal-core/run.py','ci-contract.test.py','ci-schema.py'])assert(h.steps.some(s=>s.run?.includes(token)))});
check('failure-evidence',()=>{assert(h.steps.some(s=>s.id==='public_gate'&&s.if==='always()'&&s.run?.includes('ci-evidence.py finish')));assert(h.steps.some(s=>s.uses?.startsWith('actions/upload-artifact@')&&s.if?.includes('always()')&&s.if?.includes('success')))});
check('failure-cannot-be-ignored',()=>{assert(!h['continue-on-error']);assert(h.steps.every(s=>!s['continue-on-error']));assert(h.steps.some(s=>s.if==='always()'&&s.run?.includes('ci-evidence.py assess')))});
console.log(JSON.stringify({passed:results.every(r=>r.passed),results},null,2));process.exitCode=results.some(r=>!r.passed)?1:0;
