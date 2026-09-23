"""验证 CI Git 镜像映射，使用 Git 自身解析 URL，不连接网络。"""
import os
from pathlib import Path
import re
import subprocess
import unittest

class MirrorsTest(unittest.TestCase):
    def setUp(self):
        workflow = (Path(__file__).parents[2]/'.github/workflows/build-libmpv.yml').read_text()
        job = workflow.split('  build-libmpv-external-ffmpeg:', 1)[1].split('    steps:', 1)[0]
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_CONFIG_')}
        for key, value in re.findall(r'^      (GIT_CONFIG_\w+): [\"\']?([^\n\"\']+)[\"\']?$', job, re.M):
            self.env[key] = value

    def resolve(self, url):
        return subprocess.check_output(['git', 'ls-remote', '--get-url', url], env=self.env, text=True).strip()

    def test_four_repositories_and_ffmpeg_alias(self):
        sources = {
            'https://gitlab.com/samba-team/samba.git': 'samba',
            'https://github.com/FFmpeg/FFmpeg.git': 'FFmpeg',
            'https://code.ffmpeg.org/FFmpeg/FFmpeg.git': 'FFmpeg',
            'https://github.com/mpv-ohos/libmpv-ohos-build.git': 'libmpv-ohos-build',
            'https://github.com/ErBWs/mpv.git': 'mpv',
        }
        for source, name in sources.items():
            with self.subTest(source=source):
                self.assertEqual(self.resolve(source), f'http://192.168.3.59:27134/yao/{name}.git')

    def test_other_repositories_unchanged(self):
        url = 'https://github.com/yaoshining/VidAll_Player.git'
        self.assertEqual(self.resolve(url), url)

if __name__ == '__main__':
    unittest.main()
