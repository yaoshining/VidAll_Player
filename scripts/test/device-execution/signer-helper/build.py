#!/usr/bin/env python3
"""仅在本地/云端编译辅助 class；输出身份清单，不在 iMac 自动调用。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

JAR_SHA256 = 'a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d'
HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(jar, javac, out):
    if jar.is_symlink() or not jar.is_file() or sha(jar) != JAR_SHA256:
        raise ValueError('signer-jar-mismatch')
    if out.exists():
        raise ValueError('refuse-existing-output')
    out.mkdir(mode=0o700, parents=True)
    command = [str(javac), '--release', '17', '-cp', str(jar), '-d', str(out), str(HERE/'ActualSigner.java')]
    subprocess.run(command, check=True, timeout=60, capture_output=True)
    version = subprocess.run([str(javac), '-version'], check=True, timeout=10, capture_output=True, text=True)
    manifest = {'schemaVersion': 1, 'jarSHA256': JAR_SHA256,
                'sourceSHA256': sha(HERE/'ActualSigner.java'),
                'classSHA256': sha(out/'ActualSigner.class'),
                'javacExecutableSHA256': sha(javac.resolve()),
                'javacVersion': version.stdout.strip() or version.stderr.strip(),
                'javaRelease': 17, 'deviceVerified': False, 'formalArtifactAllowed': False}
    (out/'helper-build.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--jar', type=Path, required=True)
    p.add_argument('--javac', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.jar, a.javac, a.out)))
