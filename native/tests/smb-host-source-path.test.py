"""执行 host 源码准备入口，复现依赖构建切换 cwd 后的相对路径错误。"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


class HostSourcePathTest(unittest.TestCase):
    def test_relative_entry_after_directory_change(self):
        source = (Path(__file__).parents[1] / 'scripts/build-libsmbclient-controlled.sh').read_text()
        startup = source.split('# ---------------- 可配置入口 ----------------')[0]
        host = source.split('build_host_tools() {', 1)[1].split('  ( cd "$SAMBA_HOST_DIR"', 1)[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / 'native/scripts'
            scripts.mkdir(parents=True)
            (scripts / 'fetch-locked-source.py').write_text('')
            (root / 'dependency-build').mkdir()
            # 只替代下载器；路径解析、目录切换和 host 入口使用真实 shell。
            probe = startup + '\nlog() { :; }\n' + 'build_host_tools() {' + host + '}\n'
            probe += '''python3() {
  test "$1" = "$EXPECTED_HELPER" && test -f "$1"
}
SAMBA_HOST_DIR="$PWD/host"
SAMBA_COMMIT=3984b04d7085c428ab3126ef4cfac2a396b5b29e
cd dependency-build
build_host_tools
'''
            (scripts / 'probe.sh').write_text(probe)
            result = subprocess.run(['bash', 'native/scripts/probe.sh'], cwd=root,
                                    env={**os.environ, 'EXPECTED_HELPER': str((scripts / 'fetch-locked-source.py').resolve())},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
