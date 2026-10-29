// 历史配方只追溯；活动来源门禁必须真实保留producer、完整契约及双平台元数据。
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const yaml=require('../../scripts/test/normal-core/node_modules/yaml');
const root=path.resolve(__dirname,'../..');
const history=fs.readFileSync(root+'/specs/010-cloud-build-device-execution/history/build-libmpv.pre-cloud.yml');
const tokens=['bash native/tests/capability-evidence.test.sh','bash native/tests/contract-baseline.test.sh','bash native/tests/controlled-release.test.sh','bash native/tests/build-libmpv-bootstrap.test.sh','bash native/tests/build-libmpv-patches.test.sh','bash native/tests/build-libmpv-workflow.test.sh','python3 native/tests/git-mirrors.test.py','python3 native/tests/fetch-locked-source.test.py','python3 native/tests/finalize-ohcodec-prefix.test.py','python3 native/tests/check-ohcodec-runtime.test.py','bash native/tests/libmpv-packaging.test.sh','node native/tests/cloud-source-workflow.test.cjs'];
const commands={
 'npm ci':'npm ci --prefix scripts/test/normal-core --ignore-scripts --no-audit --no-fund',
 'python3 -B scripts/test/cloud-build/producer-input.py':'python3 -B scripts/test/cloud-build/producer-input.py --out "$RUNNER_TEMP/producer-input"',
 'native/scripts/generate-libmpv-manifest.sh':'native/scripts/generate-libmpv-manifest.sh --lock native/config/sources.lock.json --source "$AUDIT_DIR/source" --output "$AUDIT_DIR/feature-manifest.json" --abi arm64-v8a --min-sdk 15 --build-time 0',
 'native/scripts/generate-sbom.sh':'native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format spdx --output "$AUDIT_DIR/sbom.spdx.json"',
 'native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format spdx':'native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format spdx --output "$AUDIT_DIR/sbom.spdx.json"',
 'native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format cyclonedx':'native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format cyclonedx --output "$AUDIT_DIR/sbom.cdx.json"',
 'native/scripts/audit-licenses.sh':'native/scripts/audit-licenses.sh --lock native/config/sources.lock.json --output "$AUDIT_DIR/license-audit.json"',
 'native/scripts/collect-licenses.sh':'native/scripts/collect-licenses.sh --lock native/config/sources.lock.json --output "$AUDIT_DIR/NOTICE"'
};
function executed(step,token){const lines=step.run.split('\n').map(s=>s.trim()).filter(s=>s&&!s.startsWith('#'));assert(lines.every(s=>!s.includes('||')&&!s.includes('&&')&&!/^(if|case|for|while|until)\b/.test(s)));assert(lines.includes(commands[token]||token),token);}
function requiredStep(job,token){const found=job.steps.filter(s=>s.run?.includes(token));assert.equal(found.length,1,token);const s=found[0];assert(!Object.hasOwn(s,'if'));assert(!s['continue-on-error']);executed(s,token);return s;}
// 有限已审Shell程序白名单；不尝试用子串检查解释任意Shell。
const frozenRuns={
  "native-contracts": {
    "安装已有锁定的YAML契约依赖": "npm ci --prefix scripts/test/normal-core --ignore-scripts --no-audit --no-fund",
    "锁定当前producer交付，未来核心更新须独立目标证据": "python3 -B scripts/test/cloud-build/producer-input.py --out \"$RUNNER_TEMP/producer-input\"",
    "验证能力证据门禁": "bash native/tests/capability-evidence.test.sh",
    "验证 SDK 候选契约基线": "bash native/tests/contract-baseline.test.sh",
    "验证受控发布工具": "bash native/tests/controlled-release.test.sh",
    "验证既有补丁与打包约束": "bash native/tests/build-libmpv-bootstrap.test.sh\nbash native/tests/build-libmpv-patches.test.sh\nbash native/tests/build-libmpv-workflow.test.sh\npython3 native/tests/git-mirrors.test.py\npython3 native/tests/fetch-locked-source.test.py\npython3 native/tests/finalize-ohcodec-prefix.test.py\npython3 native/tests/check-ohcodec-runtime.test.py\nbash native/tests/libmpv-packaging.test.sh\nnode native/tests/cloud-source-workflow.test.cjs\n"
  },
  "clean-environment": {
    "验证锁定来源与生成制品": "rm -rf \"$AUDIT_DIR\"\nmkdir -p \"$AUDIT_DIR/source/mpv\" \"$AUDIT_DIR/source/ffmpeg\"\nprintf '%s\\n' --enable-static > \"$AUDIT_DIR/source/ffmpeg/configure-options.txt\"\nprintf '%s\\n' -Dgpl=true > \"$AUDIT_DIR/source/mpv/meson-options.txt\"\nnative/scripts/generate-libmpv-manifest.sh --lock native/config/sources.lock.json --source \"$AUDIT_DIR/source\" --output \"$AUDIT_DIR/feature-manifest.json\" --abi arm64-v8a --min-sdk 15 --build-time 0\nnative/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format spdx --output \"$AUDIT_DIR/sbom.spdx.json\"\nnative/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format cyclonedx --output \"$AUDIT_DIR/sbom.cdx.json\"\nnative/scripts/audit-licenses.sh --lock native/config/sources.lock.json --output \"$AUDIT_DIR/license-audit.json\"\nnative/scripts/collect-licenses.sh --lock native/config/sources.lock.json --output \"$AUDIT_DIR/NOTICE\"\ntest -s \"$AUDIT_DIR/NOTICE\"\n",
    "说明交叉构建门禁": "echo '源码生产职责已转交ohos_ijkplayer；本任务保留锁定、来源、许可证及双平台元数据契约，不冒称最新normal核心完整目标重建通过。'"
  }
};
function verify(w,h=history){
 assert(!Object.hasOwn(w,"defaults"));
 for(const [id,j] of Object.entries(w.jobs)){assert(!Object.hasOwn(j,"defaults"));for(const step of j.steps){assert(!Object.hasOwn(step,"shell"));if(step.run!==undefined)assert.equal(step.run,frozenRuns[id]?.[step.name],step.name);}}
 assert.equal(crypto.createHash('sha256').update(h).digest('hex'),'7a6e121a449cd32a8536d8277c41835496ffd556347df735b52345551cccda99');
 assert.deepEqual(Object.keys(w.jobs).sort(),['clean-environment','native-contracts']);
 assert.deepEqual(w.permissions,{actions:'read',contents:'read'});
 for(const event of ['pull_request','push'])for(const p of ['native/**','release/inputs/004-normal-core/**','scripts/test/cloud-build/**','specs/010-cloud-build-device-execution/history/**'])assert(w.on[event].paths.includes(p));
 const n=w.jobs['native-contracts'],c=w.jobs['clean-environment'];
 for(const j of [n,c]){assert(!Object.hasOwn(j,'if'));assert(!j['continue-on-error']);for(const s of j.steps){assert(!Object.hasOwn(s,'if'));assert(!s['continue-on-error']);}}
 assert.equal(n['runs-on'],'ubuntu-22.04');assert(n.steps.some(s=>s.uses==='actions/setup-node@v4'&&s.with?.['node-version']==='22'));
 const install=requiredStep(n,'npm ci --prefix scripts/test/normal-core --ignore-scripts --no-audit --no-fund');
 const producer=requiredStep(n,'python3 -B scripts/test/cloud-build/producer-input.py');assert(n.steps.indexOf(install)<n.steps.indexOf(producer));
 for(const t of tokens)requiredStep(n,t);
 assert.equal(c.needs,'native-contracts');assert.equal(c['runs-on'],'${{ matrix.os }}');assert.deepEqual(c.strategy,{ 'fail-fast':false,matrix:{os:['macos-14','ubuntu-22.04']}});
 const meta=requiredStep(c,'native/scripts/generate-libmpv-manifest.sh');
 for(const t of ['native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format spdx','native/scripts/generate-sbom.sh --lock native/config/sources.lock.json --format cyclonedx','native/scripts/audit-licenses.sh','native/scripts/collect-licenses.sh','test -s "$AUDIT_DIR/NOTICE"'])executed(meta,t);
 assert.equal(meta.env.AUDIT_DIR,'${{ runner.temp }}/libmpv-release-audit');
 const uploads=c.steps.filter(s=>s.uses==='actions/upload-artifact@v4');assert.equal(uploads.length,1);assert.equal(uploads[0].with['if-no-files-found'],'error');assert.equal(uploads[0].with.path,'${{ runner.temp }}/libmpv-release-audit');assert(uploads[0].with.name.includes('${{ matrix.os }}'));
 assert(!JSON.stringify(w).includes('self-hosted'));assert(!JSON.stringify(w).includes('GIT_CONFIG_VALUE_'));
}
const original=yaml.parse(fs.readFileSync(root+'/.github/workflows/build-libmpv.yml','utf8'));verify(original);
const mutations={jobSkip:w=>w.jobs['native-contracts'].if='false',jobIgnore:w=>w.jobs['native-contracts']['continue-on-error']=true,producerMissing:w=>w.jobs['native-contracts'].steps=w.jobs['native-contracts'].steps.filter(s=>!s.run?.includes('producer-input.py')),stepSkip:w=>requiredStep(w.jobs['native-contracts'],tokens[0]).if='false',stepIgnore:w=>requiredStep(w.jobs['native-contracts'],tokens[0])['continue-on-error']=true,missingLegacy:w=>requiredStep(w.jobs['native-contracts'],tokens[2]).run='echo omitted',missingInstall:w=>requiredStep(w.jobs['native-contracts'],'npm ci').run='echo omitted',brokenNeeds:w=>delete w.jobs['clean-environment'].needs,onePlatform:w=>w.jobs['clean-environment'].strategy.matrix.os.pop(),excludedPlatform:w=>w.jobs['clean-environment'].strategy.matrix.exclude=[{os:'macos-14'}],metadataSkip:w=>w.jobs['clean-environment'].steps.find(s=>s.run?.includes('generate-libmpv-manifest')).if='false',missingLicense:w=>{const s=requiredStep(w.jobs['clean-environment'],'native/scripts/audit-licenses.sh');s.run=s.run.replace('native/scripts/audit-licenses.sh','echo omitted')},missingSBOM:w=>{const s=requiredStep(w.jobs['clean-environment'],'native/scripts/generate-sbom.sh');s.run=s.run.replace('--format cyclonedx','--format omitted')},uploadMissing:w=>w.jobs['clean-environment'].steps=w.jobs['clean-environment'].steps.filter(s=>!s.uses?.includes('upload-artifact')),uploadWarn:w=>w.jobs['clean-environment'].steps.find(s=>s.uses?.includes('upload-artifact')).with['if-no-files-found']='warn',uploadIgnore:w=>w.jobs['clean-environment'].steps.find(s=>s.uses?.includes('upload-artifact'))['continue-on-error']=true,uploadSkip:w=>w.jobs['clean-environment'].steps.find(s=>s.uses?.includes('upload-artifact')).if='false'};
for(const [name,change] of Object.entries(mutations)){const w=structuredClone(original);change(w);assert.throws(()=>verify(w),undefined,name);}
for(const [name,transform] of Object.entries({comment:line=>'# '+line,echo:line=>'echo '+JSON.stringify(line),ignore:line=>line+' || true'})){
 const w=structuredClone(original);const step=requiredStep(w.jobs['native-contracts'],tokens[2]);step.run=step.run.replace(tokens[2],transform(tokens[2]));assert.throws(()=>verify(w),undefined,name);
}
const controls={setPlusE:w=>{const s=requiredStep(w.jobs['native-contracts'],tokens[2]);s.run='set +e\n'+s.run+'\necho success';},shellOverride:w=>requiredStep(w.jobs['native-contracts'],tokens[2]).shell='bash {0}',jobDefaults:w=>w.jobs['native-contracts'].defaults={run:{shell:'bash {0}'}},globalDefaults:w=>w.defaults={run:{shell:'bash {0}'}},earlyExit:w=>{const s=requiredStep(w.jobs['native-contracts'],tokens[2]);s.run='exit 0\n'+s.run;},heredoc:w=>{const s=requiredStep(w.jobs['native-contracts'],tokens[2]);s.run="cat <<'EOF'\n"+s.run+'\nEOF';}};
for(const [name,change] of Object.entries(controls)){const w=structuredClone(original);change(w);assert.throws(()=>verify(w),undefined,name);}
assert.throws(()=>verify(original,Buffer.concat([history,Buffer.from('changed')])));
console.log(JSON.stringify({passed:true,rejectedMutations:Object.keys(mutations).length+Object.keys(controls).length+4,legacyCommands:11,historicalRecipeSHA256:crypto.createHash('sha256').update(history).digest('hex')}));
