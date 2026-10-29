#!/usr/bin/env python3
"""宿主统一门禁：失败非零；编译副本与二进制留在 work，仅整理文本至 public。"""
import argparse, hashlib, json, os, platform, re, shutil, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    work, public = out/'work', out/'public'
    work.mkdir(); public.mkdir()
    env = os.environ.copy()
    env.setdefault('TYPESCRIPT_PATH', str(ROOT/'scripts/test/normal-core/node_modules/typescript'))
    if not env.get('LLVM_NM'):
        nm = shutil.which('llvm-nm')
        if not nm and platform.system() == 'Darwin':
            nm = '/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/llvm-nm'
        env['LLVM_NM'] = nm or 'llvm-nm'
    rows = []
    def run(name, command, expected=0, timeout=90):
        started = time.monotonic()
        try:
            proc = subprocess.run([str(x) for x in command], cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
            code, log = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            code = 'timeout'
            decode = lambda value: value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
            log = decode(exc.stdout) + decode(exc.stderr) + '\n' + str(exc)
        except OSError as exc:
            code, log = 'launch-error', str(exc)
        (work/(name+'.log')).write_text(log)
        passed = code == expected
        rows.append({'name': name, 'exit': code, 'expectedExit': expected, 'passed': passed, 'seconds': round(time.monotonic()-started, 3)})
        print(f'{name}: {"PASS" if passed else "FAIL"} (exit={code}, expected={expected})', flush=True)
        return passed
    py = [sys.executable, '-B']
    run('public-gate-tests', py+['scripts/test/normal-core/check-public.test.py'])
    run('har-normalization-tests', py+['scripts/test/normal-core/normalize-har.test.py'])
    run('tools', ['clang++', '--version'])
    run('llvm-nm-version', [env['LLVM_NM'], '--version'])
    run('node-version', ['node', '--version'])
    run('typescript-version', ['node', '-e', 'const t=require(process.env.TYPESCRIPT_PATH); console.log(t.version); if(t.version!=="5.6.3")process.exit(1)'])
    run('input-audit', py+['scripts/audit/normal-core-verify.py'])
    run('input-mutations', py+['native/tests/normal-core-input.test.py'])
    ets_cases = ['unconfigured', 'configure', 'resource-failed', 'notifications', 'cached', 'late', 'released', 'fatal-release', 'fatal-queue', 'fatal-diagnostics', 'late-load', 'bridge-callback-fail', 'bridge-create-fail', 'bridge-pending-create', 'bridge-callback-terminal']
    for case in ets_cases:
        run('ets-'+case, ['node', 'native/tests/normal-runtime.test.cjs', case])
    run('diagnostics-session', ['node', 'native/tests/diagnostics-session.test.cjs'])
    run('diagnostics-probe-contract', ['node', 'native/tests/diagnostics-device.test.cjs'])
    common = ['clang++', '-std=c++17', '-pthread', '-Irelease/inputs/004-normal-core/include']
    if run('diagnostics-compile', common+['-Inative/diagnostics', 'native/tests/diagnostics_test.cpp', '-o', work/'diagnostics']):
        run('diagnostics-native', [work/'diagnostics'])
    if run('runtime-compile', common+['-DVIDALL_MPV_AVAILABLE=1', '-Inative/runtime', 'native/tests/normal-process-runtime.test.cpp', 'native/runtime/process_runtime.cpp', '-o', work/'runtime']):
        for case in ['normal', 'no-policy', 'abi', 'register', 'enable', 'smb', 'invalid-config', 'invalid-deadline', 'resources-rejected', 'directory-missing', 'directory-file', 'directory-symlink', 'config-corrupt']:
            run('runtime-'+case, [work/'runtime', case, work/('runtime-'+case)])
    run('native-entry', py+['native/tests/normal-native-entry.test.py', work/'native-entry'])
    parent = work/'parent-chain'
    run('parent-green', py+['native/tests/normal-parent-chain/run.py', '--out', parent/'green-final'])
    for name, mutation, cases in [
        ('mutant-guards-final', 'destroy-guards', ['terminal-render-tail', 'terminal-during-render-free']),
        ('mutant-immediate-final', 'deadline-immediate', ['terminal-callback-delivery-blocked', 'terminal-logger-blocked']),
        ('mutant-missing-final', 'deadline-missing', ['terminal-callback-delivery-blocked', 'terminal-logger-blocked'])]:
        cmd = py+['native/tests/normal-parent-chain/run.py', '--out', parent/name, '--mutate', mutation]
        for case in cases: cmd += ['--case', case]
        run(name, cmd, expected=1)
    run('parent-verification', py+['native/tests/normal-parent-chain/verify-results.py', parent])
    summary = {'passed': all(r['passed'] for r in rows), 'platform': platform.system(), 'architecture': platform.machine(), 'formalArtifactAllowed': False, 'checks': rows,
               'limits': ['仅宿主测试，不代表 HarmonyOS 目标构建或真机验收', '平台 API 为替身；没有真实 GPU 故障注入', '输入来源封存及库身份已核对；CI 不重建 producer，不重验本机外部来源路径', '保留真实父级函数、线程、引用和独立 native deadline；完整 RenderLoop 不在提取范围']}
    (work/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    # 仅允许测试输出白名单；不递归上传工作目录、输入锁、库、媒体、凭据或签名。
    selected = list(work.glob('*.log'))+[work/'summary.json']
    selected += list((work/'native-entry').glob('results.json'))
    for stage in ['green-final', 'mutant-guards-final', 'mutant-immediate-final', 'mutant-missing-final']:
        folder = parent/stage
        selected += list(folder.glob('*.log'))+list(folder.glob('results.json'))
    bindings = {}
    for file in [ROOT/'native/runtime/process_runtime.cpp', ROOT/'packages/vidall-player/src/main/cpp/napi_init.cpp', ROOT/'release/inputs/004-normal-core/manifest.json', ROOT/'scripts/test/normal-core/package-lock.json']:
        if file.is_file(): bindings[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    (public/'source-identities.json').write_text(json.dumps(bindings, indent=2)+'\n')
    for src in selected:
        text = src.read_text()
        text = text.replace(str(out), '<EVIDENCE>').replace(str(ROOT), '<REPO>')
        text = re.sub(r'/(?:private/tmp|Users|Applications|home/runner|tmp)/[^\s"\'<>]*', '<HOST_PATH>', text)
        dst = public/src.relative_to(work)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
    gate = subprocess.run(py+['scripts/test/normal-core/check-public.py', str(public)], cwd=ROOT, capture_output=True, text=True)
    print(gate.stdout, flush=True)
    return 0 if summary['passed'] and gate.returncode == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
