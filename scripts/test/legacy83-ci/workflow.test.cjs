// CI 必须在 Player 当前提交完成测试、构建与校验后上传；不得触发其他项目。
const fs = require('node:fs');
const assert = require('node:assert/strict');
const yaml = require('yaml');
const text = fs.readFileSync('.github/workflows/test-player.yml', 'utf8');
const w = yaml.parse(text);
assert.deepEqual(w.on.push.branches, ['codex/legacy-rotation-completion-84', 'codex/legacy-vulkan-size-83']);
const job = w.jobs['legacy-har'];
assert.deepEqual(job['runs-on'], ['self-hosted', 'macOS', 'deveco']);
assert.equal(job.environment, undefined);
const steps = job.steps;
const at = name => steps.findIndex(s => s.id === name);
// GitHub 只在步骤环境中提供 runner 上下文，作业环境不支持它。
assert(!JSON.stringify(job.env || {}).includes('runner.'));
assert.equal(steps[at('audit')].env.RUNNER_ENVIRONMENT, '${{ runner.environment }}');
assert(at('tests') >= 0 && at('tests') < at('build') && at('build') < at('audit') && at('audit') < at('har'));
for (const suite of ['surface-resize/gl.test.py', 'surface-resize/sw.test.py', 'completion-event.test.py']) {
  assert(steps[at('tests')].run.includes(suite));
}
assert.match(steps[at('har')].with.name, /^legacy84-ci-har-/);
assert.equal(steps[at('har')].if, 'success()');
assert.match(steps[at('build')].run, /build --modules vidall_player@default/);
assert.match(steps[at('audit')].run, /legacy83-ci\/audit.py/);
assert(!/repository_dispatch|gh workflow|ohos_ijkplayer|build-libmpv-controlled|ffmpeg.*configure/.test(text));
assert.equal(w.permissions.contents, 'read');
console.log('PASS CI 顺序、产物门禁和项目边界');
