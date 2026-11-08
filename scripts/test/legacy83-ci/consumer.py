"""在 CI 的独立目录只用待交付 HAR 编译消费者，并比对打入 HAP 的库。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('work', type=Path)
parser.add_argument('node', type=Path)
parser.add_argument('cli', type=Path)
args = parser.parse_args()
work = args.work.resolve()
shutil.copytree(root / 'examples/consumer-smoke', work,
                ignore=shutil.ignore_patterns('build', 'oh_modules', '.hvigor', '*lock.json5'))
har = work / 'candidate/vidall-player.har'
shutil.copyfile(root / 'packages/vidall-player/build/default/outputs/default/vidall_player.har', har)
for manifest in [work / 'oh-package.json5', work / 'entry/oh-package.json5']:
    config = json.loads(manifest.read_text())
    config['dependencies']['@vidall/player'] = f'file:{har}'
    manifest.write_text(json.dumps(config))
profile = work / 'build-profile.json5'
config = json.loads(profile.read_text())
del config['app']['products'][0]['signingConfig']
profile.write_text(json.dumps(config))
subprocess.run([args.node, args.cli, 'build', '--modules', 'entry@default'], cwd=work, check=True)
hap = work / 'entry/build/default/outputs/default/entry-default-unsigned.hap'
with tarfile.open(har) as package, zipfile.ZipFile(hap) as app:
    libs = json.loads((Path(__file__).parent / 'inputs.json').read_text())['libraries']
    for name in libs:
        actual = hashlib.sha256(app.read(name)).digest()
        if actual != hashlib.sha256(package.extractfile('package/' + name).read()).digest():
            raise ValueError(f'独立消费包的库与 HAR 不同：{name}')
print('独立消费工程编译通过，HAP 中五个原生库与 CI HAR 逐字节一致')
