"""候选清单与源库、HAR 实物绑定的回归测试。"""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCRIPT = Path(__file__).with_name('verify-candidate-integrity.py')


class CandidateIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = b'source with debug symbols'
        self.packed = b'stripped library'
        (self.root / 'libmpv.so').write_bytes(self.source)
        self.write_har()
        self.manifest = {
            'candidateId': 'test-candidate',
            'loadingBoundary': {'cmakeLogic': {'arm64_v8a': {
                'libmpvSource': 'libmpv.so',
                'libmpvSha256': hashlib.sha256(self.source).hexdigest(),
                'libmpvStrippedSha256': hashlib.sha256(self.packed).hexdigest(),
            }}},
            'arm64Deliverables': {'har': {
                'path': 'player.har', 'sizeBytes': (self.root / 'player.har').stat().st_size,
            }},
        }

    def write_har(self, members=1):
        with tarfile.open(self.root / 'player.har', 'w') as archive:
            for _ in range(members):
                info = tarfile.TarInfo('package/libs/arm64-v8a/libmpv.so')
                info.size = len(self.packed)
                archive.addfile(info, io.BytesIO(self.packed))

    def run_check(self, expected):
        path = self.root / 'candidate.json'
        (self.root / 'audit.json').unlink(missing_ok=True)
        path.write_text(json.dumps(self.manifest))
        result = subprocess.run([
            sys.executable, str(SCRIPT), '--root', str(self.root),
            '--manifest', str(path), '--output', str(self.root / 'audit.json'),
        ], capture_output=True, text=True, cwd='/')
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        audit = json.loads((self.root / 'audit.json').read_text())
        self.assertEqual(audit['status'], 'passed' if expected == 0 else 'failed')
        return audit

    def test_source_and_stripped_have_separate_hashes(self):
        self.run_check(0)

    def test_replaced_source_is_rejected(self):
        (self.root / 'libmpv.so').write_bytes(b'new binary')
        audit = self.run_check(1)
        self.assertFalse(audit['checks']['sourceSha256']['matches'])

    def test_replaced_har_library_is_rejected(self):
        self.packed = b'another library'
        self.write_har()
        audit = self.run_check(1)
        self.assertFalse(audit['checks']['harLibmpvSha256']['matches'])

    def test_wrong_har_size_is_rejected(self):
        self.manifest['arm64Deliverables']['har']['sizeBytes'] += 1
        self.run_check(1)

    def test_full_har_digest_matches(self):
        self.manifest['schemaVersion'] = 2
        self.manifest['arm64Deliverables']['har']['sha256'] = hashlib.sha256(
            (self.root / 'player.har').read_bytes()).hexdigest()
        self.run_check(0)

    def test_full_har_digest_mismatch_is_rejected(self):
        self.manifest['schemaVersion'] = 2
        self.manifest['arm64Deliverables']['har']['sha256'] = '0' * 64
        audit = self.run_check(1)
        self.assertFalse(audit['checks']['harSha256']['matches'])

    def test_unknown_schema_cannot_skip_full_digest(self):
        self.manifest['schemaVersion'] = 3
        self.run_check(1)

    def test_source_path_must_remain_inside_root(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / 'library'
            path.write_bytes(self.source)
            (self.root / 'external').symlink_to(path)
            self.manifest['loadingBoundary']['cmakeLogic']['arm64_v8a']['libmpvSource'] = 'external'
            self.run_check(1)

    def test_current_schema_requires_full_har_digest(self):
        self.manifest['schemaVersion'] = 2
        self.run_check(1)

    def test_missing_source_is_rejected(self):
        (self.root / 'libmpv.so').unlink()
        self.run_check(1)

    def test_missing_har_is_rejected(self):
        (self.root / 'player.har').unlink()
        self.run_check(1)

    def test_missing_or_duplicate_har_library_is_rejected(self):
        for count in (0, 2):
            with self.subTest(count=count):
                self.write_har(count)
                self.run_check(1)

    def test_aliased_duplicate_library_is_rejected(self):
        with tarfile.open(self.root / 'player.har', 'a') as archive:
            alias = tarfile.TarInfo('package/libs//arm64-v8a/libmpv.so')
            archive.addfile(alias)
        self.manifest['arm64Deliverables']['har']['sizeBytes'] = (self.root / 'player.har').stat().st_size
        self.run_check(1)

    def test_invalid_archive_is_rejected(self):
        (self.root / 'player.har').write_bytes(b'invalid archive')
        self.run_check(1)

    def test_missing_hash_is_rejected(self):
        del self.manifest['loadingBoundary']['cmakeLogic']['arm64_v8a']['libmpvSha256']
        self.run_check(1)

    def test_truncated_hash_is_rejected(self):
        self.manifest['loadingBoundary']['cmakeLogic']['arm64_v8a']['libmpvSha256'] = '99204080'
        self.run_check(1)

    def test_invalid_manifest_is_rejected(self):
        self.manifest = []
        self.run_check(1)

    def test_output_cannot_overwrite_inputs(self):
        path = self.root / 'candidate.json'
        path.write_text(json.dumps(self.manifest))
        for target in (path, self.root / 'libmpv.so', self.root / 'player.har'):
            with self.subTest(target=target.name):
                before = target.read_bytes()
                result = subprocess.run([
                    sys.executable, str(SCRIPT), '--root', str(self.root),
                    '--manifest', str(path), '--output', str(target),
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
