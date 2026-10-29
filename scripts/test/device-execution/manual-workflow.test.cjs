// 解析真实YAML及负例，保证手动入口不变为签名/设备执行或任意PR代码入口。
const fs=require('fs'),path=require('path'),assert=require('assert');
const yaml=require('../normal-core/node_modules/yaml');
const crypto=require('crypto');
const file=process.argv[2]||path.resolve(__dirname,'../../../.github/workflows/device-evidence-manual.yml');
function verify(w){
 assert.deepEqual(Object.keys(w.on),['workflow_dispatch']);assert.deepEqual(Object.keys(w.on.workflow_dispatch.inputs).sort(),['mode','request','request_sha256']);
 assert.deepEqual(w.on.workflow_dispatch.inputs.mode.options,['prepare','collect']);assert.deepEqual(w.permissions,{contents:'read',actions:'read'});
 const p=w.jobs.prepare,c=w.jobs.collect;assert.equal(p['runs-on'],'ubuntu-24.04');assert.equal(c.environment,'device-evidence-read');assert.equal(c.concurrency['cancel-in-progress'],false);
 assert(c.if.includes("vars.VIDALL_DEVICE_COLLECT_ENABLED == 'true'")&&c.if.includes('vars.VIDALL_DEVICE_COLLECT_WORKFLOW_SHA == github.sha')&&c.if.includes("github.ref == 'refs/heads/main'"));
 assert(p.if.includes("github.ref == 'refs/heads/main'"));assert.deepEqual(c['runs-on'],['self-hosted','macOS','X64','vidall-device-evidence']);
 assert(!c.steps.some(x=>x.uses?.startsWith('actions/checkout')));assert(!JSON.stringify(c).includes('secrets.')&&!JSON.stringify(c).includes('github.token'));
 assert(p.steps.some(x=>x.uses?.startsWith('actions/checkout')&&x.with['persist-credentials']===false));
 assert.equal(c.steps.length,3);
 const collect=c.steps.find(x=>x.id==='collect');assert.equal(crypto.createHash('sha256').update(collect.run).digest('hex'),'6c93a95f4bd3b6af5da4daca5769f11ceacb2bf5ccd98390350b6ffd04ba42ef');assert(collect.run.includes('/usr/bin/shasum -a 256')&&collect.run.includes('VIDALL_DEVICE_COLLECTOR_SHA256')&&collect.run.includes('manual-workflow.py" collect'));
 for(const job of [p,c]){
  assert(!job['continue-on-error']);assert(job['timeout-minutes']<=10);assert(job.steps.every(x=>!x['continue-on-error']));
  const up=job.steps.find(x=>x.uses?.startsWith('actions/upload-artifact'));assert(up);assert.equal(up.with['retention-days'],7);assert.equal(up.with['if-no-files-found'],'error');assert(up.with.path.endsWith('/public/result.json'));assert(!up.with.path.includes('**'));
  assert(job.steps.some(x=>x.name==='清理本轮公开临时目录'&&x.if==='always()'));
  for(const step of job.steps){if(step.run)assert(!step.run.includes('${{ inputs.'));assert(!/\b(hdc|sign-app|sign-verify-only|uninstall)\b/.test(step.run||''));}
 }
 const host=yaml.parse(fs.readFileSync(path.resolve(__dirname,'../../../.github/workflows/deveco26-pr82-gates.yml'),'utf8'));assert(host.jobs['host-contracts'].steps.some(x=>x.run?.includes('manual-workflow.test.py')&&x.run.includes('manual-workflow.test.cjs')));
}
const original=yaml.parse(fs.readFileSync(file,'utf8'));verify(original);
const mutants=[w=>w.on.push={},w=>w.permissions.contents='write',w=>w.jobs.collect.if='true',w=>w.jobs.collect.steps.unshift({uses:'actions/checkout@v4'}),w=>w.jobs.collect.env={TOKEN:'${{ secrets.PASSWORD }}'},w=>w.jobs.collect.steps.find(x=>x.id==='collect').run='echo ok',w=>w.jobs.collect.steps.find(x=>x.uses?.startsWith('actions/upload-artifact')).with.path='state/**',w=>w.jobs.collect.concurrency['cancel-in-progress']=true,w=>w.jobs.prepare.steps[0].run='echo ${{ inputs.request }}'];
for(const f of mutants){let w=structuredClone(original);f(w);assert.throws(()=>verify(w));}
console.log(JSON.stringify({passed:true,mutationsRejected:mutants.length,scope:'local static workflow only; remote deployment not enabled'}));

module.exports={verify};
