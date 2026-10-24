// 云端职责迁移：解析真实workflow；旧目标退役不能丢独有检查或让skip变绿。
const fs=require('fs'),path=require('path'),assert=require('assert');
const yaml=require('../normal-core/node_modules/yaml');
const root=path.resolve(__dirname,'../../..');
function verify(all){
 for(const w of Object.values(all))for(const j of Object.values(w.jobs))assert(!JSON.stringify(j['runs-on']).includes('self-hosted'),'构建仍派发self-hosted');
 const old=all['normal-core.yml'];assert.deepEqual(Object.keys(old.on),['workflow_dispatch']);assert(!old.jobs['target-har']&&!old.jobs['normal-core-result']);
 const source=all['build-libmpv.yml'];assert(!source.jobs['build-libmpv-external-ffmpeg']&&!source.jobs['cross-build-prerequisites']);
 assert(source.jobs['native-contracts']&&source.jobs['clean-environment']);assert(JSON.stringify(source).includes('cloud-build/producer-input.py'));
 const gate=all['deveco26-pr82-gates.yml'],host=gate.jobs['host-contracts'],target=gate.jobs['target-har'];
 assert.equal(target['runs-on'],'macos-26');assert(target.if.includes('vars.DEVECO26_APPROVED_EVENT_SHA == github.sha'));assert.equal(target.environment,'deveco26-build');
 for(const id of ['native_legacy','producer_input'])assert(host.steps.some(s=>s.id===id&&!s.if&&!s['continue-on-error']));
 assert(target.steps.some(s=>s.id==='hypium'&&s.run.includes('cloud-build/hypium.py')&&!s.if&&!s['continue-on-error']));
 assert(target.steps.find(s=>s.id==='hypium').run.indexOf('signing')<0);
 const tests=all['test-player.yml'];assert(Object.values(tests.jobs).some(j=>j.steps.some(s=>s.run?.includes('cloud-build/host.py'))));assert(!JSON.stringify(tests).match(/check_signing|signing_ready|\.ohos\/config/));
}
const all=Object.fromEntries(fs.readdirSync(root+'/.github/workflows').filter(n=>n.endsWith('.yml')).map(n=>[n,yaml.parse(fs.readFileSync(root+'/.github/workflows/'+n,'utf8'))]));
verify(all);
const mutants=[a=>a['normal-core.yml'].on.pull_request={},a=>a['test-player.yml'].jobs[Object.keys(a['test-player.yml'].jobs)[0]]['runs-on']=['self-hosted','macos','deveco'],a=>delete a['build-libmpv.yml'].jobs['native-contracts'],a=>delete a['build-libmpv.yml'].jobs['clean-environment'],a=>a['deveco26-pr82-gates.yml'].jobs['host-contracts'].steps=a['deveco26-pr82-gates.yml'].jobs['host-contracts'].steps.filter(s=>s.id!=='native_legacy'),a=>a['deveco26-pr82-gates.yml'].jobs['host-contracts'].steps=a['deveco26-pr82-gates.yml'].jobs['host-contracts'].steps.filter(s=>s.id!=='producer_input'),a=>a['deveco26-pr82-gates.yml'].jobs['target-har'].steps.find(s=>s.id==='hypium').if='false',a=>a['deveco26-pr82-gates.yml'].jobs['target-har'].steps.find(s=>s.id==='hypium')['continue-on-error']=true];
for(const change of mutants){const a=structuredClone(all);change(a);assert.throws(()=>verify(a));}
console.log(JSON.stringify({passed:true,rejectedMutations:mutants.length}));
