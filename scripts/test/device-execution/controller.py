#!/usr/bin/env python3
"""Spec010 制品预检与本机互斥；不签名、不安装，不产生真机通过结论。"""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_MEMBERS = 4096
REPOSITORY = 'yaoshining/VidAll_Player'
REPOSITORY_ID = 1307243374
LIBRARIES = {'libavcodec.so.62', 'libavfilter.so.11', 'libavformat.so.62', 'libavutil.so.60', 'libc++_shared.so', 'libmpv.so', 'libswresample.so.6', 'libswscale.so.9', 'libvidall_player_native.so'}
API = {'minAPIVersion': 50003015, 'targetAPIVersion': 60002022}
SOURCE_KEYS = {'repositoryId', 'repository', 'workflowPath', 'workflowSHA', 'runId', 'runAttempt', 'event', 'headSHA', 'eventMergeSHA', 'sourceTreeSHA', 'sourceTrackedBytesSHA256', 'toolchainLockSHA256', 'releaseSourceLockSHA256', 'inputHAR_SHA256'}
MANIFEST_KEYS = {'schemaVersion', 'source', 'hap', 'bundleName', 'moduleName', 'abilityName', 'api', 'libraries', 'media', 'test'}

class ContractError(ValueError):
    pass

class DeviceBusy(ContractError):
    pass

def require(condition, code):
    if not condition:
        raise ContractError(code)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def is_hash(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None

def positive_integer(value):
    return type(value) is int and value > 0

def read_file(path, limit=MAX_ARCHIVE):
    """不跟随末级符号链接；先核大小再有界读取。"""
    fd = None
    try:
        fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit, 'file-type-or-size')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            data = stream.read(limit + 1)
        require(len(data) == info.st_size and len(data) <= limit, 'file-changed-or-too-large')
        return data
    except OSError as error:
        raise ContractError('file-unavailable') from error
    finally:
        if fd is not None:
            os.close(fd)

def read_json(data):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate-json-key')
            result[key] = value
        return result
    try:
        result = json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ContractError('non-finite-json')))
    except (UnicodeError, ValueError) as error:
        raise ContractError('invalid-json') from error
    require(isinstance(result, dict), 'json-not-object')
    return result

def read_zip_members(data):
    """只在内存读取，永不extractall；ZIP及展开总量均受限。"""
    require(0 < len(data) <= MAX_ARCHIVE, 'archive-size')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            require(0 < len(infos) <= MAX_MEMBERS, 'archive-member-count')
            require(sum(info.file_size for info in infos) <= MAX_EXPANDED, 'archive-expanded-size')
            result = {}
            for info in infos:
                name = info.filename
                clean = name[:-1] if info.is_dir() else name
                require(name == info.orig_filename and '\x00' not in name and '\\' not in name and ':' not in name,
                        'archive-path')
                path = PurePosixPath(clean)
                require(bool(clean) and not path.is_absolute() and '..' not in path.parts and str(path) == clean,
                        'archive-path')
                require(name not in result, 'archive-duplicate-member')
                kind = stat.S_IFMT(info.external_attr >> 16)
                require(kind in (0, stat.S_IFREG, stat.S_IFDIR), 'archive-special-member')
                require((kind != stat.S_IFDIR or info.is_dir()) and (not info.is_dir() or info.file_size == 0),
                        'archive-directory')
                require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        'archive-encoding')
                require(0 <= info.file_size <= MAX_ARCHIVE, 'archive-member-size')
                content = archive.read(info)
                require(len(content) == info.file_size, 'archive-member-length')
                result[name] = content
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as error:
        raise ContractError('invalid-archive') from error

def validate_source(source):
    require(isinstance(source, dict) and set(source) == SOURCE_KEYS, 'source-fields')
    require(source['repository'] == REPOSITORY and source['repositoryId'] == REPOSITORY_ID, 'repository')
    require(positive_integer(source['runId']) and positive_integer(source['runAttempt']), 'run-identity')
    require(source['event'] in ('pull_request', 'workflow_dispatch', 'push', 'merge_group'), 'event')
    require(isinstance(source['workflowPath'], str) and re.fullmatch(r'\.github/workflows/[A-Za-z0-9_-]+\.yml', source['workflowPath']), 'workflow-path')
    for field in ['workflowSHA', 'headSHA', 'eventMergeSHA', 'sourceTreeSHA']:
        require(is_hash(source[field], 40), 'source-commit')
    # merge queue 的 head 是实际 group checkout，不得借用其中某个 PR 的 head。
    if source['event'] == 'merge_group':
        require(source['headSHA'] == source['eventMergeSHA'], 'merge-group-checkout')
    for field in ['sourceTrackedBytesSHA256', 'toolchainLockSHA256', 'releaseSourceLockSHA256', 'inputHAR_SHA256']:
        require(is_hash(source[field]), 'source-digest')

def verify_hap(data, manifest):
    require(manifest['api'] == API, 'approved-api')
    require(isinstance(manifest['bundleName'], str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){2,}', manifest['bundleName']), 'bundle-format')
    require(manifest['moduleName'] == 'entry' and manifest['abilityName'] == 'EntryAbility', 'entry-policy')
    members = read_zip_members(data)
    require('module.json' in members, 'module-missing')
    metadata = read_json(members['module.json'])
    app = metadata.get('app', {})
    module = metadata.get('module', {})
    require(isinstance(app, dict) and isinstance(module, dict), 'module-format')
    require(app.get('bundleName') == manifest['bundleName'] and module.get('name') == manifest['moduleName'], 'actual-bundle-module')
    require({key: app.get(key) for key in API} == API, 'actual-api')
    abilities = module.get('abilities')
    require(isinstance(abilities, list) and len(abilities) == 1 and isinstance(abilities[0], dict) and abilities[0].get('name') == manifest['abilityName'], 'actual-ability')
    expected = manifest['libraries']
    require(isinstance(expected, dict) and set(expected) == LIBRARIES and all(is_hash(v) for v in expected.values()), 'library-policy')
    actual = {}
    for name, content in members.items():
        if name.startswith('libs/') and not name.endswith('/'):
            require(name.startswith('libs/arm64-v8a/') and name.count('/') == 2, 'library-architecture')
            actual[name.rsplit('/', 1)[1]] = digest(content)
    require(actual == expected, 'actual-libraries')
    media = manifest['media']
    require(isinstance(media, dict) and set(media) == {'path', 'bytes', 'sha256', 'generatorSHA256', 'parameters', 'origin'}, 'media-fields')
    require(media['path'] == 'resources/rawfile/test_video.mp4' and media['origin'] == 'generated-synthetic', 'media-policy')
    require(positive_integer(media['bytes']) and is_hash(media['sha256']) and is_hash(media['generatorSHA256']), 'media-digest')
    require(isinstance(media['parameters'], list) and 0 < len(media['parameters']) <= 32 and all(isinstance(v, str) and len(v) <= 256 for v in media['parameters']), 'media-parameters')
    require(media['path'] in members and len(members[media['path']]) == media['bytes'] and digest(members[media['path']]) == media['sha256'], 'actual-media')
    test = manifest['test']
    require(isinstance(test, dict) and set(test) == {'mode', 'entrySourceSHA256', 'privateNasAllowed', 'freshSessionRequired'}, 'test-fields')
    require(test['mode'] == 'normal-local-smoke' and is_hash(test['entrySourceSHA256']) and test['privateNasAllowed'] is False and test['freshSessionRequired'] is True, 'test-policy')
    return actual

def verify_artifact(artifact, approval, expected_approval_sha256):
    """expected_approval_sha256须由外部审批提供，不能从approval自己取值。"""
    require(is_hash(expected_approval_sha256), 'external-approval-required')
    approval_bytes = read_file(approval, 256 * 1024)
    require(digest(approval_bytes) == expected_approval_sha256, 'external-approval-mismatch')
    envelope = read_json(approval_bytes)
    fields = {'schemaVersion', 'source', 'artifactId', 'zipSHA256', 'manifestSHA256', 'approvedBundleName', 'approvedMode', 'github'}
    require(set(envelope) == fields and type(envelope['schemaVersion']) is int and envelope['schemaVersion'] == 1, 'approval-fields')
    source = envelope['source']; validate_source(source)
    require(positive_integer(envelope['artifactId']) and is_hash(envelope['zipSHA256']) and is_hash(envelope['manifestSHA256']), 'artifact-identity')
    github = envelope['github']
    expected_github = {key: source[key] for key in ['repositoryId', 'runId', 'runAttempt', 'headSHA', 'eventMergeSHA', 'workflowPath', 'workflowSHA']}
    expected_github.update(artifactId=envelope['artifactId'], conclusion='success', expired=False, digest='sha256:' + envelope['zipSHA256'])
    require(isinstance(github, dict) and github == expected_github, 'github-readback-mismatch')
    data = read_file(artifact)
    require(digest(data) == envelope['zipSHA256'], 'artifact-digest')
    members = read_zip_members(data)
    require(set(members) == {'manifest.json', 'device-unsigned.hap'}, 'artifact-members')
    require(len(members['manifest.json']) <= 256 * 1024 and digest(members['manifest.json']) == envelope['manifestSHA256'], 'manifest-digest')
    manifest = read_json(members['manifest.json'])
    require(set(manifest) == MANIFEST_KEYS and type(manifest['schemaVersion']) is int and manifest['schemaVersion'] == 1, 'manifest-fields')
    require(manifest['source'] == source, 'manifest-source')
    require(isinstance(manifest['test'], dict), 'test-fields')
    require(manifest['bundleName'] == envelope['approvedBundleName'] and manifest['test'].get('mode') == envelope['approvedMode'], 'approved-package-policy')
    hap = manifest['hap']
    require(isinstance(hap, dict) and set(hap) == {'path', 'bytes', 'sha256'} and hap['path'] == 'device-unsigned.hap', 'hap-fields')
    require(positive_integer(hap['bytes']) and is_hash(hap['sha256']) and len(members[hap['path']]) == hap['bytes'] and digest(members[hap['path']]) == hap['sha256'], 'hap-digest')
    libraries = verify_hap(members[hap['path']], manifest)
    return {'artifactVerified': True, 'deviceVerified': False, 'formalArtifactAllowed': False, 'artifactId': envelope['artifactId'], 'runId': source['runId'], 'runAttempt': source['runAttempt'], 'headSHA': source['headSHA'], 'eventMergeSHA': source['eventMergeSHA'], 'approvalSHA256': expected_approval_sha256, 'zipSHA256': envelope['zipSHA256'], 'manifestSHA256': envelope['manifestSHA256'], 'unsignedHAP_SHA256': hap['sha256'], 'bundleName': manifest['bundleName'], 'libraries': libraries, 'mediaSHA256': manifest['media']['sha256']}

def compare_signed_payload(unsigned, signed):
    """HAP签名块不属于ZIP成员；任何新增/删除/修改成员都不能豁免。"""
    before = read_zip_members(read_file(unsigned))
    after = read_zip_members(read_file(signed))
    require(set(before) == set(after), 'signed-payload-members')
    require(all(before[name] == after[name] for name in before), 'signed-payload-changed')
    return {'payloadEqual': True, 'membersCompared': len(before), 'signatureVerified': False, 'deviceVerified': False, 'formalArtifactAllowed': False, 'nextRequired': 'official-verify-app-with-approved-certificate-profile-and-device'}

class DeviceLease:
    """固定设备路径的真实进程锁；保留锁inode，退出只解锁不unlink。"""
    def __init__(self, path):
        self.path = Path(path)
        self.fd = None

    def __enter__(self):
        try:
            parent = self.path.parent.stat()
            require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.geteuid() and not parent.st_mode & 0o022, 'lock-parent-permissions')
            self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            info = os.fstat(self.fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid() and not info.st_mode & 0o077, 'lock-file-permissions')
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise DeviceBusy('device-busy') from error
            return self
        except (OSError, ContractError) as error:
            if self.fd is not None:
                os.close(self.fd); self.fd = None
            if isinstance(error, ContractError):
                raise
            raise ContractError('lock-unavailable') from error

    def __exit__(self, *unused):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd); self.fd = None

def preflight(artifact, approval, expected_approval_sha256, lock_path, device_state='unknown', signing_configuration=None):
    """仅验证制品并检查互斥；device_state为观察输入，不是本程序实测。"""
    result = verify_artifact(artifact, approval, expected_approval_sha256)
    result.update(status='pending', signedInstallable=False, deviceStateIndependentlyVerified=False, deviceState=device_state,
                  mutations=['local-exclusive-lock-only'], deviceVerified=False)
    try:
        with DeviceLease(lock_path):
            if device_state != 'connected':
                reason = {'offline': 'device-offline', 'unauthorized': 'device-unauthorized'}.get(device_state, 'device-state-unverified')
            elif signing_configuration is None:
                reason = 'signing-material-missing'
            else:
                reason = 'official-signature-verifier-not-connected'
    except DeviceBusy:
        reason = 'device-busy'
    result['pendingReason'] = reason
    result['nextRequired'] = ['fresh-device-tool-identity-and-state', 'approved-signing-material-and-official-verification', 'reviewed-install-run-cleanup-adapter']
    return result

def main():
    parser = argparse.ArgumentParser(description='只读制品预检和本机锁检查；未实现签名/安装/执行，pending返回2。')
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--approval-sha256', required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--device-state', choices=['unknown', 'connected', 'offline', 'unauthorized'], default='unknown')
    args = parser.parse_args()
    try:
        result = preflight(args.artifact, args.approval, args.approval_sha256, args.lock, args.device_state)
    except (ContractError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'failed', 'reason': str(error) if isinstance(error, ContractError) else 'malformed-contract', 'deviceVerified': False, 'formalArtifactAllowed': False}))
        return 1
    print(json.dumps(result))
    return 2

if __name__ == '__main__':
    raise SystemExit(main())
