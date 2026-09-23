"""隔离继承的 Git 定位变量，并覆盖暂存目录与移动失败分支。"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).parents[1]/'scripts/build-libsmbclient-controlled.sh').read_text()
STARTUP = SOURCE.split('# ---------------- 可配置入口 ----------------')[0]
FUNCTIONS = SOURCE.split('# ---------------- 源码检出 ----------------')[1].split('# ---------------- 依赖链构建 ----------------')[0]

class SafetyTest(unittest.TestCase):
    def test_git_environment_cannot_redirect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
            for name in ('target','foreign'):
                subprocess.run(['git','init','-q',str(root/name)],env=env,check=True)
            env.update({key:str(root/'foreign'/'.git') for key in
                ('GIT_DIR','GIT_COMMON_DIR','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES')})
            env.update(GIT_WORK_TREE=str(root/'foreign'),GIT_INDEX_FILE=str(root/'foreign/index'),GIT_NAMESPACE='foreign',GIT_PREFIX='foreign/')
            env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='url.http://mirror/.insteadOf',GIT_CONFIG_VALUE_0='https://upstream/')
            shell = STARTUP + '\ngit -C "$1" rev-parse --show-toplevel\ngit ls-remote --get-url https://upstream/repo\n'
            result = subprocess.run(['bash','-c',shell,'probe',str(root/'target')],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.splitlines(),[str((root/'target').resolve()),'http://mirror/repo'])

    def probe_failure(self, mode):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); target=root/'cache'; target.mkdir(); (target/'old').write_text('keep')
            shell='set -euo pipefail\n'+FUNCTIONS+'''
git() { return 1; }
mktemp() { if [ "$MODE" = temp ]; then return 1; fi; command mktemp "$@"; }
python3() {
  while [ "$1" != --destination ]; do shift; done
  # 测试不得触碰 /source；只在受控根目录内模拟下载。
  case "$2" in "$ROOT"/*) mkdir -p "$2";; *) echo unsafe > "$ROOT/unsafe"; return 1;; esac
}
mv() {
  case "$MODE:$1" in
    initial:"$TARGET") return 1;;
    publish:*/source|rollback:*/source|rollback:*/previous) return 1;;
  esac
  command mv "$@"
}
ensure_samba_source "$TARGET" || exit 7
'''
            result=subprocess.run(['bash','-c',shell],env={**os.environ,'ROOT':str(root),'TARGET':str(target),'MODE':mode,'SMB_SCRIPT_DIR':str(root),'SAMBA_COMMIT':'a'*40},capture_output=True,text=True)
            self.assertEqual(result.returncode,7,result.stderr)
            self.assertFalse((root/'unsafe').exists())
            if mode == 'rollback':
                backups=list(root.glob('cache.fetch.*/previous/old'))
                self.assertEqual(len(backups),1)
                self.assertEqual(backups[0].read_text(),'keep')
            else:
                self.assertEqual((target/'old').read_text(),'keep')
                self.assertEqual(list(root.iterdir()),[target])

    def test_mktemp_failure(self): self.probe_failure('temp')
    def test_initial_move_failure(self): self.probe_failure('initial')
    def test_publish_failure_restores_cache(self): self.probe_failure('publish')
    def test_rollback_failure_keeps_backup(self): self.probe_failure('rollback')

if __name__ == '__main__': unittest.main()
