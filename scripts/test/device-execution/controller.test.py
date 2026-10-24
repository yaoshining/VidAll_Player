#!/usr/bin/env python3
"""新控制器真实函数 TDD；合成 ZIP 不冒充真实 HAP 或平台签名。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('device_controller', HERE / 'controller.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
LIBS = ['libavcodec.so.62', 'libavfilter.so.11', 'libavformat.so.62', 'libavutil.so.60', 'libc++_shared.so', 'libmpv.so', 'libswresample.so.6', 'libswscale.so.9', 'libvidall_player_native.so']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()

def archive(entries, extras=()):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for name, value in entries.items():
            z.writestr(name, value)
        for name, value in extras:
            z.writestr(name, value)
    return stream.getvalue()

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = dict(repositoryId=1307243374, repository='yaoshining/VidAll_Player', workflowPath='.github/workflows/deveco26-pr82-gates.yml', workflowSHA='a' * 40, runId=123, runAttempt=2, event='pull_request', headSHA='b' * 40, eventMergeSHA='c' * 40, sourceTreeSHA='d' * 40, sourceTrackedBytesSHA256='e' * 64, toolchainLockSHA256='f' * 64, releaseSourceLockSHA256='1' * 64, inputHAR_SHA256='2' * 64)
        self.bundle = 'com.yaoshining.deviceprobe'
        self.members = {'module.json': encoded({'app': {'bundleName': self.bundle, 'minAPIVersion': 50003015, 'targetAPIVersion': 60002022}, 'module': {'name': 'entry', 'abilities': [{'name': 'EntryAbility'}]}}), 'ets/modules.abc': b'synthetic ArkTS payload', 'resources/rawfile/test_video.mp4': b'synthetic media bytes'}
        self.members.update({'libs/arm64-v8a/' + n: ('synthetic ' + n).encode() for n in LIBS})
        self.manifest = {'schemaVersion': 1, 'source': self.source, 'hap': {'path': 'device-unsigned.hap', 'bytes': 0, 'sha256': ''}, 'bundleName': self.bundle, 'moduleName': 'entry', 'abilityName': 'EntryAbility', 'api': {'minAPIVersion': 50003015, 'targetAPIVersion': 60002022}, 'libraries': {n: sha(self.members['libs/arm64-v8a/' + n]) for n in LIBS}, 'media': {'path': 'resources/rawfile/test_video.mp4', 'bytes': len(self.members['resources/rawfile/test_video.mp4']), 'sha256': sha(self.members['resources/rawfile/test_video.mp4']), 'generatorSHA256': '3' * 64, 'parameters': ['synthetic-unit-test'], 'origin': 'generated-synthetic'}, 'test': {'mode': 'normal-local-smoke', 'entrySourceSHA256': '4' * 64, 'privateNasAllowed': False, 'freshSessionRequired': True}}
        self.artifact = self.root / 'artifact.zip'
        self.approval = self.root / 'approval.json'
        self.repack()

    def repack(self, hap_extras=(), outer_extras=()):
        hap = archive(self.members, hap_extras)
        self.manifest['hap'].update(bytes=len(hap), sha256=sha(hap))
        self.unsigned = self.root / 'unsigned.hap'
        self.unsigned.write_bytes(hap)
        manifest_bytes = encoded(self.manifest)
        data = archive({'manifest.json': manifest_bytes, 'device-unsigned.hap': hap}, outer_extras)
        self.artifact.write_bytes(data)
        self.envelope = {'schemaVersion': 1, 'source': self.source, 'artifactId': 456, 'zipSHA256': sha(data), 'manifestSHA256': sha(manifest_bytes), 'approvedBundleName': self.bundle, 'approvedMode': 'normal-local-smoke', 'github': {'repositoryId': 1307243374, 'artifactId': 456, 'runId': self.source['runId'], 'runAttempt': self.source['runAttempt'], 'headSHA': self.source['headSHA'], 'eventMergeSHA': self.source['eventMergeSHA'], 'workflowPath': self.source['workflowPath'], 'workflowSHA': self.source['workflowSHA'], 'conclusion': 'success', 'expired': False, 'digest': 'sha256:' + sha(data)}}
        self.write_approval()

    def write_approval(self):
        data = encoded(self.envelope)
        self.approval.write_bytes(data)
        self.approval_sha = sha(data)

    def verify(self):
        return C.verify_artifact(self.artifact, self.approval, self.approval_sha)

    def test_normal_artifact(self):
        result = self.verify()
        self.assertTrue(result['artifactVerified'])
        self.assertFalse(result['deviceVerified'])
        self.assertEqual(result['runAttempt'], 2)
        self.assertEqual(len(result['libraries']), 9)

    def test_absent_external_approval(self):
        for value in ['', '0' * 64, None]:
            with self.assertRaises(C.ContractError):
                C.verify_artifact(self.artifact, self.approval, value)

    def test_wrong_zip_digest(self):
        self.artifact.write_bytes(self.artifact.read_bytes() + b'changed')
        with self.assertRaises(C.ContractError): self.verify()

    def test_wrong_attempt_and_failed_source(self):
        for field, value in [('runAttempt', 1), ('conclusion', 'failure'), ('expired', True), ('headSHA', '9' * 40), ('artifactId', 789)]:
            with self.subTest(field=field):
                old = self.envelope['github'][field]
                self.envelope['github'][field] = value
                self.write_approval()
                with self.assertRaises(C.ContractError): self.verify()
                self.envelope['github'][field] = old

    def test_manifest_cannot_claim_own_artifact_digest(self):
        self.manifest['artifactId'] = 456
        self.repack()
        with self.assertRaises(C.ContractError): self.verify()

    def test_wrong_actual_bundle(self):
        data = json.loads(self.members['module.json']); data['app']['bundleName'] = 'com.other.app'
        self.members['module.json'] = encoded(data); self.repack()
        with self.assertRaises(C.ContractError): self.verify()

    def test_wrong_actual_api_or_ability(self):
        for mutate in [lambda d: d['app'].update(targetAPIVersion=60003023), lambda d: d['module'].update(abilities=[{'name': 'OtherAbility'}])]:
            with self.subTest(mutate=repr(mutate)):
                original = self.members['module.json']; data = json.loads(original); mutate(data)
                self.members['module.json'] = encoded(data); self.repack()
                with self.assertRaises(C.ContractError): self.verify()
                self.members['module.json'] = original

    def test_missing_or_modified_media(self):
        key = self.manifest['media']['path']
        for value in [None, b'changed']:
            with self.subTest(value=value):
                if value is None: self.members.pop(key)
                else: self.members[key] = value
                self.repack()
                with self.assertRaises(C.ContractError): self.verify()

    def test_private_nas_or_missing_fresh_session(self):
        for key, value in [('privateNasAllowed', True), ('freshSessionRequired', False)]:
            self.manifest['test'][key] = value; self.repack()
            with self.assertRaises(C.ContractError): self.verify()
            self.manifest['test'][key] = not value

    def test_missing_or_extra_library(self):
        self.members.pop('libs/arm64-v8a/libmpv.so'); self.repack()
        with self.assertRaises(C.ContractError): self.verify()
        self.members['libs/x86_64/unexpected.so'] = b'extra'; self.repack()
        with self.assertRaises(C.ContractError): self.verify()

    def test_path_escape_duplicates_and_symlink(self):
        for name in ['../outside', '/absolute', 'a\\b', './relative', 'double//slash']:
            with self.subTest(name=name):
                self.repack(outer_extras=[(name, b'bad')])
                with self.assertRaises(C.ContractError): self.verify()
        with self.assertWarns(UserWarning): self.repack(hap_extras=[('module.json', b'duplicate')])
        with self.assertRaises(C.ContractError): self.verify()
        zi = zipfile.ZipInfo('symlink'); zi.create_system = 3; zi.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.repack(hap_extras=[(zi, b'/outside')])
        with self.assertRaises(C.ContractError): self.verify()

    def test_no_real_signature_claim_from_payload_equality(self):
        signed = self.root / 'signed.hap'; signed.write_bytes(self.unsigned.read_bytes())
        result = C.compare_signed_payload(self.unsigned, signed)
        self.assertTrue(result['payloadEqual'])
        self.assertFalse(result['signatureVerified'])
        self.assertFalse(result['deviceVerified'])

    def test_signed_changed_or_added_members_rejected(self):
        signed = self.root / 'signed.hap'
        for changes in [{'ets/modules.abc': b'changed code'}, {'META-INF/FAKE.SF': b'not exempt'}]:
            members = dict(self.members); members.update(changes); signed.write_bytes(archive(members))
            with self.assertRaises(C.ContractError): C.compare_signed_payload(self.unsigned, signed)

    def test_actual_process_lock_and_cleanup(self):
        path = self.root / 'device.lock'
        with C.DeviceLease(path):
            with self.assertRaises(C.DeviceBusy):
                with C.DeviceLease(path): pass
        with C.DeviceLease(path): pass
        self.assertTrue(path.exists(), '锁文件保留，避免unlink导致不同inode双持锁')

    def test_lock_symlink_rejected(self):
        original = self.root / 'original'; original.write_text('do not modify')
        link = self.root / 'link'; link.symlink_to(original)
        with self.assertRaises(C.ContractError):
            with C.DeviceLease(link): pass
        self.assertEqual(original.read_text(), 'do not modify')

    def test_preflight_never_accepts_claimed_signing(self):
        for device in ['offline', 'unauthorized', 'unknown', 'connected']:
            for signing in [None, {'passed': True, 'signatureVerified': True}]:
                with self.subTest(device=device, signing=signing):
                    result = C.preflight(self.artifact, self.approval, self.approval_sha, self.root / 'device.lock', device, signing)
                    self.assertEqual(result['status'], 'pending')
                    self.assertFalse(result['deviceVerified'])
                    self.assertFalse(result['signedInstallable'])
                    self.assertFalse(result['deviceStateIndependentlyVerified'])

    def test_preflight_busy(self):
        with C.DeviceLease(self.root / 'device.lock'):
            result = C.preflight(self.artifact, self.approval, self.approval_sha, self.root / 'device.lock', 'connected', None)
        self.assertEqual(result['pendingReason'], 'device-busy')
        self.assertFalse(result['deviceVerified'])

    def test_cli_pending_not_exit_zero(self):
        command = [sys.executable, '-B', str(HERE / 'controller.py'), '--artifact', str(self.artifact), '--approval', str(self.approval), '--approval-sha256', self.approval_sha, '--lock', str(self.root / 'cli.lock'), '--device-state', 'connected']
        result = subprocess.run(command, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout); self.assertFalse(report['deviceVerified'])
        self.assertEqual(report['pendingReason'], 'signing-material-missing')

    def test_malformed_test_returns_contract_error(self):
        for value in [None, [], 'invalid']:
            self.manifest['test'] = value; self.repack()
            with self.assertRaises(C.ContractError): self.verify()

    def test_boolean_schema_is_not_version_one(self):
        self.envelope['schemaVersion'] = True; self.write_approval()
        with self.assertRaises(C.ContractError): self.verify()
        self.manifest['schemaVersion'] = True; self.repack()
        with self.assertRaises(C.ContractError): self.verify()

    def test_archive_limits_and_duplicate_json(self):
        data = archive({'one': b'abc', 'two': b'def'})
        for variable, limit in [('MAX_ARCHIVE', len(data) - 1), ('MAX_MEMBERS', 1), ('MAX_EXPANDED', 5)]:
            with self.subTest(variable=variable), patch.object(C, variable, limit):
                with self.assertRaises(C.ContractError): C.read_zip_members(data)
        for bad in [b'{"key": 1,"key": 2}', b'{"key": NaN}', b'[]']:
            with self.assertRaises(C.ContractError): C.read_json(bad)

    def test_separate_process_observes_busy_lock(self):
        path = self.root / 'separate-process.lock'
        command = [sys.executable, '-B', str(HERE / 'controller.py'), '--artifact', str(self.artifact), '--approval', str(self.approval), '--approval-sha256', self.approval_sha, '--lock', str(path), '--device-state', 'connected']
        with C.DeviceLease(path):
            result = subprocess.run(command, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['pendingReason'], 'device-busy')

if __name__ == '__main__':
    unittest.main()
