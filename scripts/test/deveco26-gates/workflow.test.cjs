// 解析实际新workflow，变异必须被拒；不把本地模拟当GitHub审批配置。
const fs=require('fs'),path=require('path'),assert=require('assert');
const yaml=require('../normal-core/node_modules/yaml');
const file=process.argv[2]||path.resolve(__dirname,'../../../.github/workflows/deveco26-pr82-gates.yml');
function verify(w){
 assert(w.on.pull_request.branches.includes('main'));assert(!w.on.pull_request.paths);assert(w.on.merge_group.types.includes('checks_requested'));assert(w.on.push.branches.includes('main'));assert(!w.on.pull_request_target);
 const h=w.jobs['host-contracts'],t=w.jobs['target-har'],r=w.jobs['deveco26-result'];assert.equal(t['runs-on'],'macos-26');assert.equal(t.environment,'deveco26-build');
 assert.equal(t.if,"(github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository) && vars.DEVECO26_APPROVED_EVENT_SHA != '' && vars.DEVECO26_APPROVED_EVENT_SHA == github.sha");
 assert(!JSON.stringify(h).includes('secrets.'));assert(!JSON.stringify(w.env||{}).includes('secrets.'));assert(!JSON.stringify(t.env||{}).includes('secrets.'));assert.deepEqual(w.permissions,{contents:'read'});
 const bootstrap=t.steps.find(s=>s.id==='bootstrap');assert.deepEqual(Object.keys(bootstrap.env),['DEVECO26_RELEASE_READ_TOKEN']);for(const step of t.steps)if(step!==bootstrap)assert(!JSON.stringify(step).includes('secrets.'));
 for(const j of [h,t]){assert(!j['continue-on-error']);assert(j.steps.every(s=>!s['continue-on-error']));const checkout=j.steps.find(s=>s.uses?.startsWith('actions/checkout@'));assert(checkout);assert(!checkout.with.ref);assert.equal(checkout.with['fetch-depth'],0);assert.equal(checkout.with['persist-credentials'],false);assert(j.steps.some(s=>s.run?.includes('ci-context.py')))}
 const dependencyRun=h.steps.find(s=>s.id==='dependencies').run;
 const install=dependencyRun.match(/^\s*sudo apt-get install -y ([^\n]+)$/m);assert(install,'missing Ubuntu dependency install');
 const packages=install[1].trim().split(/\s+/);for(const name of ['clang','llvm','cmake','ripgrep'])assert(packages.includes(name),'missing Ubuntu host dependency '+name);
 const targetDependencies=t.steps.find(s=>s.id==='runtime').run;assert(targetDependencies.includes('if ! command -v rg >/dev/null 2>&1; then brew install ripgrep; fi'));assert(targetDependencies.includes('rg --version'));assert(targetDependencies.includes('packaging-dependencies.log'));
 const reviewContracts=h.steps.find(s=>s.id==='contracts');
 for(const name of ['pr-review-runtime','har-native-packaging'])assert(reviewContracts.run.includes('python3 -B native/tests/'+name+'.test.py 2>&1 | tee'), 'missing PR review contract '+name);
 assert(h.steps.some(s=>s.run?.includes('normal-core/run.py')));assert(h.steps.some(s=>s.run?.includes('deveco26-gates/gates.test.py')));
 for(const id of ['context','trust','bootstrap','runtime','target','api_negative','consumer','cleanup','public_gate','assess'])assert(t.steps.some(s=>s.id===id));
 assert(t.steps.find(s=>s.id==='target').run.includes('deveco26/evaluate.py build'));assert(t.steps.find(s=>s.id==='consumer').run.includes('deveco26-gates/consumer.py'));assert(t.steps.find(s=>s.id==='trust').run.includes('deveco26-gates/gates.py trust'));
 const consumerRun=t.steps.find(s=>s.id==='consumer').run;assert(consumerRun.includes('set -euo pipefail'));assert(consumerRun.includes('har-native-packaging.test.sh --artifacts'));assert(consumerRun.includes('har-packaging-artifacts.log'));
 assert.equal(t.steps.find(s=>s.id==='bootstrap').env.DEVECO26_RELEASE_READ_TOKEN,'${{ secrets.DEVECO26_RELEASE_READ_TOKEN }}');
 assert(t.steps.find(s=>s.id==='bootstrap').run.includes('deveco26/release-source.py'));
 assert(h.steps.some(s=>s.run?.includes('deveco26/release-source.test.py')));
 for(const id of ['cleanup','public_gate','assess'])assert.equal(t.steps.find(s=>s.id===id).if,'always()');
 assert(t.steps.find(s=>s.id==='public_gate').run.includes('gates.py finish'));assert(t.steps.find(s=>s.id==='assess').run.includes('gates.py assess'));
 const upload=t.steps.find(s=>s.uses?.startsWith('actions/upload-artifact@'));assert.equal(upload.if,"always() && steps.public_gate.outcome == 'success'");assert.equal(upload.with.path,'${{ env.CI_OUT }}/public/');
 assert.equal(r.if,'always()');assert.deepEqual([...r.needs].sort(),['host-contracts','target-har']);assert(r.steps.some(s=>s.run?.includes('gates.py verdict')));
}
const original=yaml.parse(fs.readFileSync(file,'utf8'));verify(original);
const mutations=[w=>w.jobs['target-har'].steps=w.jobs['target-har'].steps.filter(s=>s.id!=='api_negative'),w=>delete w.on.pull_request,w=>delete w.on.merge_group,w=>w.on.pull_request_target={},w=>w.jobs['target-har'].if='true',w=>delete w.jobs['target-har'].environment,w=>w.jobs['target-har'].steps[0].with.ref='${{ github.event.pull_request.head.sha }}',w=>w.jobs['target-har'].steps=w.jobs['target-har'].steps.filter(s=>s.id!=='consumer'),w=>w.jobs['target-har'].steps.find(s=>s.id==='cleanup').if='success()',w=>w.jobs['target-har'].steps.find(s=>s.id==='public_gate').if='success()',w=>w.jobs['target-har']['continue-on-error']=true,w=>w.jobs['deveco26-result'].needs=['host-contracts'],w=>w.jobs['deveco26-result'].if='success()',w=>w.jobs['target-har'].steps.find(s=>s.uses?.startsWith('actions/upload-artifact@')).with.path='${{ env.CI_OUT }}/',w=>w.jobs['host-contracts'].env={TOKEN:'${{ secrets.DEVECO26_ARCHIVE_URL }}'}];
mutations.push(w=>w.jobs['target-har'].steps.find(s=>s.id==='bootstrap').run='python3 scripts/test/deveco26/bootstrap.py prepare',w=>w.jobs['target-har'].steps.find(s=>s.id==='runtime').env={TOKEN:'${{ secrets.DEVECO26_RELEASE_READ_TOKEN }}'},w=>w.jobs['target-har'].env={TOKEN:'${{ secrets.DEVECO26_RELEASE_READ_TOKEN }}'},w=>w.env={TOKEN:'${{ secrets.DEVECO26_RELEASE_READ_TOKEN }}'},w=>w.permissions.contents='write',w=>w.jobs['host-contracts'].steps.find(s=>s.id==='contracts').run=w.jobs['host-contracts'].steps.find(s=>s.id==='contracts').run.replace('deveco26/release-source.test.py','deveco26/omitted.py'));
for(const name of ['pr-review-runtime','har-native-packaging'])mutations.push(w=>{const step=w.jobs['host-contracts'].steps.find(s=>s.id==='contracts');step.run=step.run.replace(name+'.test.py','omitted.test.py');});
mutations.push(w=>{const step=w.jobs['target-har'].steps.find(s=>s.id==='consumer');step.run=step.run.replace('har-native-packaging.test.sh --artifacts','omitted.sh --artifacts');});
mutations.push(w=>{const step=w.jobs['host-contracts'].steps.find(s=>s.id==='dependencies');step.run=step.run.replace(/\bripgrep\b/g,'');});
mutations.push(w=>{const step=w.jobs['target-har'].steps.find(s=>s.id==='runtime');step.run=step.run.replace('brew install ripgrep','true');});
for(const mutation of mutations){const w=structuredClone(original);mutation(w);assert.throws(()=>verify(w));}
console.log(JSON.stringify({passed:true,mutationsRejected:mutations.length,scope:'local workflow structure; remote environment protection pending'}));
