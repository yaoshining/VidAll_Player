// 手动云构建从 main 固定控制脚本和 SDK，再检出用户选择的仓内提交。
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const yaml = require('../normal-core/node_modules/yaml');
const workflow = yaml.parse(fs.readFileSync(path.resolve(__dirname, '../../../.github/workflows/deveco26-evaluation.yml'), 'utf8'));
function verify(w) {
  assert.deepEqual(Object.keys(w.on), ['workflow_dispatch']);
  assert(w.on.workflow_dispatch.inputs.branch.required);
  assert.equal(w.jobs.resolve.if, "github.ref == 'refs/heads/main'");
  const job = w.jobs.evaluation;
  assert.equal(job.needs, 'resolve');
  assert.equal(job.environment, 'deveco26-build');
  assert.equal(job['runs-on'], 'macos-26');
  const steps = job.steps;
  const prepare = steps.findIndex(s => s.id === 'bootstrap');
  const source = steps.findIndex(s => s.id === 'source');
  assert(prepare > 0 && source > prepare);
  assert.equal(steps[source].with.ref, '${{ needs.resolve.outputs.commit }}');
  assert.equal(steps[source].with['persist-credentials'], false);
  assert.equal(steps[prepare].env.DEVECO26_RELEASE_READ_TOKEN, '${{ secrets.DEVECO26_RELEASE_READ_TOKEN }}');
  for (const step of steps.filter(s => s.id !== 'bootstrap')) assert(!JSON.stringify(step).includes('secrets.'));
  assert.equal(steps.find(s => s.id === 'cleanup').if, 'always()');
  assert(steps.findIndex(s => s.id === 'upload') > steps.findIndex(s => s.id === 'cleanup'));
}
verify(workflow);
for (const mutate of [w => w.on.push={}, w => w.jobs.resolve.if='true', w => delete w.jobs.evaluation.environment,
  w => w.jobs.evaluation.steps.find(s => s.id === 'source').with.ref='${{ inputs.branch }}']) {
  const changed=structuredClone(workflow); mutate(changed); assert.throws(() => verify(changed));
}
console.log('手动云构建来源、审批和分支锁定检查通过');
