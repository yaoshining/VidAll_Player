// CI 必须在 Player 当前提交完成测试、构建与校验后上传；不得触发其他项目。
const fs = require('node:fs');
const assert = require('node:assert/strict');
const yaml = require('yaml');
const text = fs.readFileSync('.github/workflows/test-player.yml', 'utf8');
const w = yaml.parse(text);
assert.deepEqual(w.on.push.branches, ['codex/legacy-vulkan-size-83']);
const steps = w.jobs['legacy-har'].steps;
const at = name => steps.findIndex(s => s.id === name);
assert(at('tests') >= 0 && at('tests') < at('build') && at('build') < at('audit') && at('audit') < at('har'));
assert.equal(steps[at('har')].if, 'success()');
assert.match(steps[at('build')].run, /build --modules vidall_player@default/);
assert.match(steps[at('audit')].run, /legacy83-ci\/audit.py/);
assert(!/repository_dispatch|gh workflow|ohos_ijkplayer|build-libmpv-controlled|ffmpeg.*configure/.test(text));
assert.equal(w.permissions.contents, 'read');
console.log('PASS CI 顺序、产物门禁和项目边界');
