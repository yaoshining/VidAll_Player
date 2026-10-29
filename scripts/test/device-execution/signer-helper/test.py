#!/usr/bin/env python3
"""真实 SID 函数、链成员误认变异和失败 CLI；无私有证书/设备操作。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('signer_build', HERE/'build.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

def run(args, timeout=60):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=timeout)

def verify(jar, javac, java, out):
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    with tempfile.TemporaryDirectory(prefix='vidall-signer-test-') as temp:
        root = Path(temp)
        classes = root/'classes'
        built = B.build(jar, javac, classes)
        (out/'helper-build.json').write_text(json.dumps(built, indent=2)+'\n')
        compiled = run([javac, '--release', '17', '-cp', str(classes)+':'+str(jar),
                        '-d', classes, HERE/'ActualSignerTest.java'])
        if compiled.returncode:
            raise RuntimeError('fixture-compile-failed')
        green = run([java, '-cp', str(classes)+':'+str(jar), 'ActualSignerTest'])
        (out/'GREEN.log').write_text(green.stdout+green.stderr)
        assert green.returncode == 0 and 'RESULT passed=12 failed=0 realHapVerified=false' in green.stdout
        rows.append({'name': 'actual-SID-twelve-cases', 'passed': True})

        # 同型错误：把批准证书仅作为 CMS Store 成员就视为实际 signer。
        source = (HERE/'ActualSigner.java').read_text()
        begin = source.index('        Collection<X509CertificateHolder> matches =')
        end = source.index('        return actual;', begin)+len('        return actual;')
        mutant = source[:begin]+'''        for (X509CertificateHolder item : result.getCertificateHolderStore().getMatches(null)) {
            if (sha(item.getEncoded()).equals(expected)) return expected;
        }
        throw new IllegalArgumentException("missing-member");'''+source[end:]
        mutant_source = root/'ActualSigner.java'
        mutant_source.write_text(mutant)
        mutant_classes = root/'mutant'
        mutant_classes.mkdir()
        compiled = run([javac, '--release', '17', '-cp', jar, '-d', mutant_classes,
                        mutant_source, HERE/'ActualSignerTest.java'])
        assert compiled.returncode == 0
        red = run([java, '-cp', str(mutant_classes)+':'+str(jar), 'ActualSignerTest'])
        (out/'MEMBERSHIP-MUTANT.log').write_text(red.stdout+red.stderr)
        assert red.returncode != 0 and 'FAIL approved-only-extra-member' in red.stdout
        rows.append({'name': 'chain-membership-mutant-rejected', 'passed': True})

        fake = root/'not-a-hap.hap'
        fake.write_bytes(b'Synthetic invalid HAP, no signing materials')
        digest = hashlib.sha256(fake.read_bytes()).hexdigest()
        link = root/'symlink.hap'
        link.symlink_to(fake)
        for name, args in [('missing-arguments', []),
                           ('wrong-hap-hash', [fake, '0'*64, '1'*64]),
                           ('actual-invalid-hap', [fake, digest, '1'*64]),
                           ('symlink-input', [link, digest, '1'*64])]:
            result = run([java, '-cp', str(classes)+':'+str(jar), 'ActualSigner', *args])
            value = json.loads(result.stdout)
            assert result.returncode == 1 and result.stderr == ''
            assert value == {'schemaVersion': 1, 'signedHAP_SHA256': '',
                             'actualSignerDER_SHA256': '', 'signerCount': 0, 'verified': False}
            rows.append({'name': name, 'passed': True})
        for name, bad_jar, bad_out in [('wrong-jar', fake, root/'wrong-jar-build'),
                                      ('existing-output', jar, classes)]:
            try:
                B.build(bad_jar, javac, bad_out)
            except ValueError:
                rows.append({'name': name, 'passed': True})
            else:
                raise AssertionError(name)
        again = B.build(jar, javac, root/'second-build')
        assert again['classSHA256'] == built['classSHA256']
        rows.append({'name': 'separate-directory-class-reproducible', 'passed': True})
    result = {'passed': True, 'checks': rows, 'sourceSHA256': B.sha(HERE/'ActualSigner.java'),
              'jarSHA256': B.JAR_SHA256, 'realHapVerified': False,
              'deviceVerified': False, 'formalArtifactAllowed': False}
    (out/'RESULT.json').write_text(json.dumps(result, indent=2)+'\n')
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('jar', 'javac', 'java', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(verify(args.jar, args.javac, args.java, args.out)))
