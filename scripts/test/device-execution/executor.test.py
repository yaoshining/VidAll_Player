#!/usr/bin/env python3
"""真实执行适配函数TDD；平台命令为替身，不声明真实签名或设备通过。"""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import subprocess
from functools import lru_cache
from unittest.mock import patch
import executor as E
from controller import ContractError, DeviceLease

def encoded(value): return (json.dumps(value, sort_keys=True) + '\n').encode()
def sha(data): return hashlib.sha256(data).hexdigest()
def hap(pages=None):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        z.writestr('module.json', b'unchanged')
        if pages is not None:z.writestr('.pages.info',pages)
    return data.getvalue()

def transaction(platform,state,binding):
    return E.transaction(platform,state,binding,execution_identity={'approvalSHA256':'d'*64,'controllerSHA256':'e'*64})

class Platform:
    """只用于验证真实事务状态机；禁止当作真机证据。"""
    def __init__(self, binding):
        self.binding = binding; self.calls = []; self.online = True; self.existing = False
        self.cleanup_valid = True; self.execution_error = False
    def connected(self): self.calls.append('connected'); return self.online
    def package_absent(self): self.calls.append('absent'); return not self.existing
    def install(self): self.calls.append('install'); self.existing = True; return {'installedPayloadVerified': True}
    def start(self): self.calls.append('start'); return self.binding
    def collect(self):
        self.calls.append('collect')
        if self.execution_error: raise TimeoutError('synthetic timeout')
        return events(self.binding)
    def cleanup(self):
        self.calls.append('cleanup')
        return {'confirmed': self.cleanup_valid, 'appSelfCleanup': 'confirmed' if self.cleanup_valid else 'unconfirmed'}

@lru_cache(maxsize=1)
def actual_trace():
    script=Path(__file__).resolve().parents[1]/'device-package/session.test.cjs'
    run=subprocess.run(['node',str(script),'--trace-json'],capture_output=True,text=True,timeout=10)
    if run.returncode: raise AssertionError('真实SmokeSession宿主trace失败: '+run.stderr)
    data=json.loads(run.stdout)
    if data.get('passed') is not True: raise AssertionError('真实SmokeSession未通过')
    return data['events']

def events(binding):
    start={'event':'session-start','cycle':0,'value':'started','elapsedMs':0}
    return [{**binding, **r, 'schemaVersion':1,'seq':i+1} for i,r in enumerate([start,*actual_trace()])]

class Tests(unittest.TestCase):
    def test_cleanup_phase_fixed_enum_and_history_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            record=E.SmokeEvidence(Path(tmp),self.request)
            for i in range(32):record.cleanup_command('window',{'returncode':0,'stdout':'synthetic','stderr':''},phase='pre-uninstall' if i<31 else 'post-uninstall')
            saved=json.loads(record.path.read_text());self.assertEqual(len(saved['cleanupCommandHistory']),32)
            self.assertEqual(saved['cleanupCommandHistory'][-1]['phase'],'post-uninstall')
            before=record.path.read_bytes()
            with self.assertRaisesRegex(ContractError,'evidence-size'):record.cleanup_command('window',phase='post-uninstall')
            self.assertEqual(before,record.path.read_bytes())
        for invalid in ['secret-phase','post-install',1,{},['pre-uninstall']]:
            with tempfile.TemporaryDirectory() as tmp:
                record=E.SmokeEvidence(Path(tmp),self.request);before=record.path.read_bytes()
                with self.assertRaisesRegex(ContractError,'evidence-fields'):record.cleanup_command('window',phase=invalid)
                self.assertEqual(before,record.path.read_bytes())

    def test_cleanup_fixed_new_failures_are_preserved_without_private_fields(self):
        value={'confirmed':False,'checks':{'pre-uninstall-window-valid':False,'cleanup-evidence-retained':False,'secret':True},'failedChecks':['pre-uninstall-window-invalid','cleanup-evidence-not-retained','secret'],'private':'do-not-save'}
        result=E.sanitized_cleanup(value)
        self.assertEqual(result['checks'],{'pre-uninstall-window-valid':False,'cleanup-evidence-retained':False})
        self.assertEqual(result['failedChecks'],value['failedChecks'][:2]);self.assertNotIn('private',result)
        for code in ['cleanup-final-deadline','cleanup-uninstall-unconfirmed']:
            self.assertEqual(E.failure_details(ContractError(code),'cleanup')['code'],code)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.binding = {'nonce': 'a'*32, 'bundle': 'com.yaoshining.vidalldeviceprobe', 'pid': 4321, 'startedAtMs': 1000000, 'unsignedHapSHA256': 'b'*64}
        self.request = {k:self.binding[k] for k in ['nonce','bundle','unsignedHapSHA256']}
        self.unsigned=self.root/'unsigned.hap'; self.signed=self.root/'signed.hap'
        self.pages=b'official synthetic pages'; self.unsigned.write_bytes(hap()); self.signed.write_bytes(hap(self.pages))
        self.cert=b'synthetic certificate DER'; self.pem=b'-----BEGIN CERTIFICATE-----\n'+base64.b64encode(self.cert)+b'\n-----END CERTIFICATE-----\n'
        self.profile=b'synthetic signed profile'; self.device='synthetic-udid'
        self.config={'bundleName':self.binding['bundle'], 'profileSHA256':sha(self.profile), 'certificateDER_SHA256':sha(self.cert), 'deviceIdSHA256':sha(self.device.encode())}
        self.tools={'java':'/approved/java','signTool':'/approved/sign.jar','signerHelperClassPath':'/approved/helper'}
        self.tools['pagesHelperClassPath']='/approved/pages-helper'
        self.config.update({'pagesInfoSHA256':sha(self.pages),'pagesInfoBytes':len(self.pages)})
        self.commands=[]; self.missing=False; self.bad_profile=False; self.wrong_cert=False; self.wrong_signer=False
    def official(self, args, timeout):
        self.commands.append(args)
        if 'ExpectedPages' in args:
            Path(args[-1]).write_bytes(self.pages)
            return {'returncode':0,'stdout':json.dumps({'schemaVersion':1,'derived':True,'unsignedHAP_SHA256':sha(self.unsigned.read_bytes()),'alignment':4,'signCode':1,'pagesSHA256':sha(self.pages),'pagesBytes':len(self.pages)}),'stderr':''}
        if 'ActualSigner' in args:
            return {'returncode':0,'stdout':json.dumps({'schemaVersion':1,'verified':True,'signerCount':1,'actualSignerDER_SHA256':'0'*64 if self.wrong_signer else sha(self.cert),'signedHAP_SHA256':sha(self.signed.read_bytes())}),'stderr':''}
        if self.bad_profile and 'verify-profile' in args: return {'returncode':1,'stdout':'','stderr':'fail'}
        if not self.missing and 'verify-app' in args:
            Path(args[args.index('-outCertChain')+1]).write_bytes(self.pem if not self.wrong_cert else b'-----BEGIN CERTIFICATE-----\nYmFk\n-----END CERTIFICATE-----\n')
            Path(args[args.index('-outProfile')+1]).write_bytes(self.profile)
        if not self.missing and 'verify-profile' in args:
            content={'type':'debug','validity':{'not-before':900,'not-after':1100},'bundle-info':{'bundle-name':self.config['bundleName'],'development-certificate':self.pem.decode()},'debug-info':{'device-id-type':'udid','device-ids':[self.device]}}
            Path(args[args.index('-outFile')+1]).write_bytes(encoded({'verifiedPassed':True,'content':content}))
        return {'returncode':0,'stdout':'','stderr':''}
    def verify(self): return E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/'verify',self.official,1000,self.device)
    def test_official_certificate_output_suffix_contract(self):
        # 同锁官方JAR真实复现要求outCertChain后缀.cer，内容仍为PEM链。
        # 证据ROOT-OFFICIAL-CERT-SUFFIX-REPRO.json；此替身严格复用该参数约束。
        def run(args,timeout):
            if 'verify-app' in args and Path(args[args.index('-outCertChain')+1]).suffix!='.cer':
                return {'returncode':1,'stdout':'','stderr':'ERROR 11012005'}
            return self.official(args,timeout)
        result=E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/'suffix',run,1000,self.device)
        self.assertTrue(result['signatureVerified'])

    def test_official_verification_and_payload(self):
        result=self.verify(); self.assertTrue(result['signatureVerified']); self.assertTrue(result['payloadEqual'])
        self.assertEqual(len(self.commands),4)

    def test_pages_helper_failure_cannot_fallback(self):
        for mode in ['failed','missing','wrong-input','wrong-content']:
            def run(args,timeout):
                if 'ExpectedPages' not in args:return self.official(args,timeout)
                if mode=='failed':return {'returncode':7,'stdout':'private text','stderr':'secret'}
                result=self.official(args,timeout)
                if mode=='missing':Path(args[-1]).unlink()
                elif mode=='wrong-input':result['stdout']=result['stdout'].replace(sha(self.unsigned.read_bytes()),'0'*64)
                else:Path(args[-1]).write_bytes(b'wrong')
                return result
            with self.subTest(mode=mode),self.assertRaises(ContractError) as caught:
                E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/mode,run,1000,self.device)
            detail=E.failure_details(caught.exception,'sign-app')
            self.assertEqual(detail['stage'],'pages-derive');self.assertNotIn('private',json.dumps(detail))

    def test_payload_diff_persisted_before_private_cleanup(self):
        with zipfile.ZipFile(self.signed,'a') as z:z.writestr('password-secret-name',b'raw-secret')
        outer=self
        class SignPlatform:
            signed_identity=None
            def connected(self):return True
            def package_absent(self):return True
            def prepare_signed(self):return outer.verify()
        try:
            result=E.sign_verify_transaction(SignPlatform(),self.root/'state',self.request)
            self.assertEqual(result['status'],'failed');self.assertTrue(self.signed.exists())
            # 与真实main相同顺序：事务先落专属JSON，外层finally再删私有输出。
            stored=json.loads((self.root/'state'/('sign-verify-'+self.request['nonce']+'.json')).read_text())
        finally:self.signed.unlink()
        self.assertFalse(self.signed.exists())
        self.assertEqual(stored['failure']['payloadDiff']['differenceCount'],1)
        self.assertNotIn('password-secret',json.dumps(stored));self.assertNotIn('raw-secret',json.dumps(stored))
        e=ContractError('signed-payload-changed');e.payload_diff={'entries':[{'name':'private-password'}]}
        self.assertNotIn('private-password',json.dumps(E.failure_details(e,'payload-compare')))

    def test_approved_certificate_is_not_actual_signer(self):
        self.wrong_signer=True
        with self.assertRaises(ContractError):self.verify()
    def test_missing_or_stale_extracted_outputs(self):
        self.missing=True
        with self.assertRaises(ContractError): self.verify()
        (self.root/'stale').mkdir(); (self.root/'stale/profile.p7b').write_bytes(self.profile)
        with self.assertRaises(ContractError): E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/'stale',self.official,1000,self.device)
    def test_wrong_certificate_and_profile_failure(self):
        self.wrong_cert=True
        with self.assertRaises(ContractError): self.verify()
        self.wrong_cert=False; self.bad_profile=True
        with self.assertRaises(ContractError): E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/'verify2',self.official,1000,self.device)
    def test_profile_expiry_and_device_mismatch(self):
        for now, device in [(1200,self.device),(1000,'other')]:
            with self.assertRaises(ContractError): E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/str(now),self.official,now,device)
    def test_payload_change_rejected(self):
        self.signed.write_bytes(self.signed.read_bytes().replace(b'unchanged',b'CHANGED!!'))
        with self.assertRaises(ContractError): self.verify()
    def test_evidence_write_failure_never_skips_cleanup(self):
        for point in ('cleanup','finish','event-validation'):
            with self.subTest(point=point),tempfile.TemporaryDirectory() as tmp:
                platform=Platform(self.binding);original=E.SmokeEvidence.checkpoint
                def checkpoint(obj,stage,failure=None):
                    if stage==point:raise OSError('secret disk path')
                    return original(obj,stage,failure)
                with patch.object(E.SmokeEvidence,'checkpoint',checkpoint),patch.object(E.SmokeEvidence,'finish',side_effect=OSError('secret') if point=='finish' else None) as finish:
                    if point!='finish':finish.side_effect=lambda *args,**kwargs:None
                    result=transaction(platform,tmp,self.request)
                self.assertIn('cleanup',platform.calls);self.assertFalse(result['scenarioPassed']);self.assertIn('evidenceFailure',result);self.assertNotIn('secret',json.dumps(result))

    def test_snapshot_known_app_error_and_final_nested_injection(self):
        row={**events(self.binding)[0],'event':'session-failed','value':'DIAGNOSTIC_UNAVAILABLE'}
        snap=E.safe_event_snapshot([row],self.binding);self.assertEqual(snap['rows'][0]['value'],'DIAGNOSTIC_UNAVAILABLE')
        with tempfile.TemporaryDirectory() as tmp:
            record=E.SmokeEvidence(Path(tmp),self.request)
            record.finish({'status':'failed','failure':{'stage':'secret','code':'secret','errorType':'secret','raw':'secret'},'cleanup':{'confirmed':False,'checks':{'secret':True},'failedChecks':['secret'],'appSelfCleanup':'secret'}})
            self.assertNotIn('secret',record.path.read_text())

    def test_transaction_identity_and_verified_signature_survive_scenario_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            platform=Platform(self.binding);platform.verification={'signatureVerified':True,'signedHAP_SHA256':'f'*64,'unsignedHAP_SHA256':self.request['unsignedHapSHA256'],'payloadEqual':True};platform.execution_error=True
            result=transaction(platform,tmp,self.request)
            record=json.loads((Path(tmp)/('smoke-'+self.request['nonce']+'.json')).read_text())
            self.assertTrue(record['signatureVerified']);self.assertTrue(record['installedPayloadVerified']);self.assertEqual(record['approvalSHA256'],'d'*64);self.assertEqual(record['controllerSHA256'],'e'*64);self.assertEqual(record['binding']['pid'],self.binding['pid']);self.assertFalse(record['scenarioPassed'])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ContractError):E.transaction(Platform(self.binding),tmp,self.request)

    def test_final_evidence_write_failure_persists_failed_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            platform=Platform(self.binding);original=E.SmokeEvidence._write
            def fail_final(record):
                if record.data.get('status')=='passed':raise OSError('disk-secret')
                return original(record)
            with patch.object(E.SmokeEvidence,'_write',fail_final):result=transaction(platform,tmp,self.request)
            self.assertFalse(result['scenarioPassed']);journal=json.loads((Path(tmp)/'journal.json').read_text())
            self.assertIn('evidenceFailure',journal)
            saved=json.loads((Path(tmp)/('smoke-'+self.request['nonce']+'.json')).read_text());self.assertNotEqual(saved['status'],'passed')

    def test_smoke_event_failure_persisted_before_cleanup(self):
        outer=self
        class Broken(Platform):
            def collect(self):
                trace=events(self.binding)
                for row in trace:
                    if row['event']=='progress':row['value']=json.dumps({'beforeMs':1000,'afterMs':1000,'intervalMs':700})
                return trace
            def cleanup(self):
                record=json.loads((outer.root/'state'/('smoke-'+outer.request['nonce']+'.json')).read_text())
                outer.assertEqual(record['failure']['code'],'progress-not-observed')
                outer.assertGreater(record['events']['count'],0)
                return super().cleanup()
        result=transaction(Broken(self.binding),self.root/'state',self.request)
        stored=json.loads((self.root/'state'/('smoke-'+self.request['nonce']+'.json')).read_text())
        self.assertEqual(result['failure']['stage'],'event-validation');self.assertEqual(stored['status'],'failed')
        self.assertFalse(stored['scenarioPassed']);self.assertTrue(stored['cleanup']['confirmed'])

    def test_smoke_success_has_independent_nonce_result(self):
        result=transaction(Platform(self.binding),self.root/'state',self.request)
        p=self.root/'state'/('smoke-'+self.request['nonce']+'.json');stored=json.loads(p.read_text())
        self.assertTrue(stored['scenarioPassed']);self.assertEqual(stored['status'],'passed')
        self.assertEqual(stored['binding']['nonce'],self.request['nonce']);self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(stored['events']['count'],len(events(self.binding)));self.assertFalse(stored['formalArtifactAllowed'])

    def test_smoke_interruption_is_recorded_before_cleanup(self):
        outer=self
        for exception in [KeyboardInterrupt,SystemExit]:
            with self.subTest(exception=exception):
                state=self.root/exception.__name__
                class Interrupted(Platform):
                    def collect(self):raise exception('password-do-not-save')
                    def cleanup(self):
                        record=json.loads((state/('smoke-'+outer.request['nonce']+'.json')).read_text())
                        outer.assertEqual(record['failure']['code'],'operation-interrupted')
                        return super().cleanup()
                try:result=transaction(Interrupted(self.binding),state,self.request)
                except (KeyboardInterrupt,SystemExit):self.fail('中断未转换为有界安全持久结果')
                text=(state/('smoke-'+self.request['nonce']+'.json')).read_text()
                self.assertEqual(result['status'],'interrupted');self.assertNotIn('password-do-not-save',text)

    def test_safe_event_snapshot_rejects_secrets_and_mixed_binding(self):
        trace=events(self.binding);trace.append({**trace[-1],'event':'private-secret-event','value':'password=/private/key','nonce':'c'*32,'seq':999})
        trace[1]['value']='password=/private/key'
        snapshot=E.safe_event_snapshot(trace,self.binding)
        encoded_snapshot=json.dumps(snapshot)
        self.assertNotIn('private-secret',encoded_snapshot);self.assertNotIn('password=',encoded_snapshot);self.assertNotIn('/private/key',encoded_snapshot)
        self.assertTrue(snapshot['rows'][-1]['bindingMismatch']);self.assertEqual(snapshot['rows'][-1]['event'],'unknown')
        self.assertLessEqual(len(snapshot['rows']),2048)

    def test_evidence_nonce_path_tamper_and_limit_fail_closed(self):
        state=self.root/'state';state.mkdir(mode=0o700)
        with self.assertRaises(ContractError):E.SmokeEvidence(state,{**self.request,'nonce':'../bad'})
        target=state/('smoke-'+self.request['nonce']+'.json');victim=self.root/'secret';victim.write_text('do-not-overwrite');target.symlink_to(victim)
        with self.assertRaises(ContractError):E.SmokeEvidence(state,self.request)
        self.assertEqual(victim.read_text(),'do-not-overwrite');target.unlink()
        record=E.SmokeEvidence(state,self.request)
        with self.assertRaises(ContractError):E.SmokeEvidence(state,self.request)
        target.write_text('tampered')
        with self.assertRaises(ContractError):record.checkpoint('collect')
        self.assertEqual(target.read_text(),'tampered')
        with self.assertRaises(ContractError):E.safe_event_snapshot([{}]*2049,self.binding)

    def test_fixed_runtime_cleanup_codes_stay_precise(self):
        codes=['installed-package-unexpectedly-absent','command-timeout','command-output-too-large',
            'device-id-query-failed','device-id-format','device-id-mismatch','fresh-device-required']
        for code in codes:
            with self.subTest(code=code):self.assertEqual(E.failure_details(ContractError(code),'cleanup')['code'],code)
        self.assertEqual(E.failure_details(ContractError('command-timeout:private-password'),'cleanup')['code'],'unclassified-contract-error')

    def test_fixed_event_error_codes_and_unknown_text(self):
        for code in ['progress-not-observed','pause-not-stable','event-session-mismatch','seek-not-observed','event-missing-or-repeated:seek-complete','session-timeout','startup-evidence-missing']:
            error=TimeoutError(code) if code.endswith('timeout') or code=='startup-evidence-missing' else ContractError(code)
            self.assertEqual(E.failure_details(error,'collect')['code'],code)
        unknown=ContractError('event-missing-or-repeated:private-password')
        detail=E.failure_details(unknown,'collect');self.assertEqual(detail['code'],'unclassified-contract-error');self.assertNotIn('private-password',json.dumps(detail))

    def test_signature_summary_does_not_claim_verification_pending(self):
        result=self.verify();self.assertTrue(result['signatureVerified'])
        self.assertNotEqual(result.get('nextRequired'),'official-verify-app-with-approved-certificate-profile-and-device')

    def test_normal_event_trace(self): self.assertTrue(E.validate_events(events(self.binding),self.binding)['passed'])
    def test_stale_or_mixed_session(self):
        for key,value in [('nonce','c'*32),('pid',999),('startedAtMs',999),('unsignedHapSHA256','d'*64)]:
            trace=events(self.binding); trace[-1][key]=value
            with self.assertRaises(ContractError): E.validate_events(trace,self.binding)
    def test_failed_missing_seek_or_unmoving_progress(self):
        traces=[]
        a=events(self.binding);a[-1]['event']='session-failed';traces.append(a)
        a=events(self.binding);a=[r for r in a if r['event']!='seek-complete'];traces.append(a)
        a=events(self.binding)
        for r in a:
            if r['event']=='progress':r['value']=json.dumps({'beforeMs':500,'afterMs':500,'intervalMs':700})
        traces.append(a)
        for trace in traces:
            with self.assertRaises(ContractError): E.validate_events(trace,self.binding)
    def test_timeout_and_wrong_pause(self):
        for field,value in [('elapsedMs',120001),('value',json.dumps({'beforeMs':1000,'afterMs':9000,'intervalMs':1000,'paused':True}))]:
            a=events(self.binding); index=-1 if field=='elapsedMs' else next(i for i,r in enumerate(a) if r['event']=='paused');a[index][field]=value
            with self.assertRaises(ContractError): E.validate_events(a,self.binding)

    def test_late_player_error_or_runtime_not_ready(self):
        a=events(self.binding);a.insert(-1,{**a[-1],'event':'player-error','value':'late-failure'})
        for i,row in enumerate(a,1):row['seq']=i
        with self.assertRaises(ContractError):E.validate_events(a,self.binding)
        a=events(self.binding);next(r for r in a if r['event']=='runtime-ready')['value']='failed'
        with self.assertRaises(ContractError):E.validate_events(a,self.binding)
    def signing_platform(self):
        p=Platform(self.binding);p.verification=None
        def prepare():p.calls.append('prepare_signed');p.verification={'signatureVerified':True,'payloadEqual':True}
        p.prepare_signed=prepare
        return p
    def test_sign_verify_only_success_never_calls_device_mutations(self):
        p=self.signing_platform();state=self.root/'state';state.mkdir();old=b'{"status":"complete","previous":"sealed"}';(state/'journal.json').write_bytes(old)
        r=E.sign_verify_transaction(p,state,self.request)
        self.assertTrue(r['signatureVerified']);self.assertFalse(r['deviceVerified']);self.assertFalse(r['scenarioPassed'])
        self.assertEqual(p.calls,['connected','absent','prepare_signed']);self.assertEqual((state/'journal.json').read_bytes(),old)
        self.assertTrue((state/('sign-verify-'+self.request['nonce']+'.json')).is_file())
        with self.assertRaises(ContractError):E.sign_verify_transaction(p,state,self.request)
    def test_sign_verify_only_failure_diagnostics_no_cleanup(self):
        p=self.signing_platform()
        def prepare():
            error=ContractError('signed-profile-mismatch');error.safe_stage='verification-identity';raise error
        p.prepare_signed=prepare;p.signed_identity={'sha256':'c'*64,'bytes':1024};r=E.sign_verify_transaction(p,self.root/'state',self.request)
        saved=json.loads((self.root/'state'/('sign-verify-'+self.request['nonce']+'.json')).read_text());self.assertEqual(saved['signedArtifact'],p.signed_identity)
        self.assertEqual(r['failure']['stage'],'verification-identity');self.assertEqual(r['failure']['code'],'signed-profile-mismatch')
        self.assertFalse(r['deviceVerified']);self.assertNotIn('install',p.calls);self.assertNotIn('cleanup',p.calls)
    def test_sign_verify_only_pending_and_existing_journal(self):
        p=self.signing_platform();p.online=False;r=E.sign_verify_transaction(p,self.root/'off',self.request)
        self.assertEqual(r['pendingReason'],'device-offline');self.assertNotIn('prepare_signed',p.calls)
        p=self.signing_platform();p.existing=True;r=E.sign_verify_transaction(p,self.root/'existing',self.request)
        self.assertEqual(r['pendingReason'],'existing-package-not-owned');self.assertNotIn('prepare_signed',p.calls)
        state=self.root/'state';state.mkdir();(state/'journal.json').write_text('{"status":"cleanup-unknown"}')
        with self.assertRaises(ContractError):E.sign_verify_transaction(self.signing_platform(),state,self.request)
    def test_sign_verify_only_unknown_error_is_redacted(self):
        p=self.signing_platform()
        def prepare():raise ContractError('password=synthetic private-profile')
        p.prepare_signed=prepare;r=E.sign_verify_transaction(p,self.root/'state',self.request)
        self.assertEqual(r['failure']['code'],'unclassified-contract-error');self.assertNotIn('password=',json.dumps(r))

    def test_transaction_preserves_safe_verification_failure(self):
        p=Platform(self.binding);self.bad_profile=True
        def install():return self.verify()
        p.install=install;r=transaction(p,self.root/'state',self.request)
        self.assertEqual(r['failure'],{'stage':'verify-profile','code':'official-tool-failed','errorType':'ContractError','exitCode':1})
        saved=json.loads((self.root/'state/journal.json').read_text())
        self.assertEqual(saved['failure'],r['failure']);self.assertTrue(r['cleanup']['confirmed'])

    def test_transaction_does_not_copy_arbitrary_error_text(self):
        secret='password=synthetic-only /private/secret profile-data'
        for i,error in enumerate([ContractError(secret),ContractError('official-tool-failed\n'+secret),OSError(secret),ValueError(secret),TimeoutError(secret)]):
            error.safe_stage=secret
            p=Platform(self.binding)
            def install(error=error):raise error
            p.install=install;r=transaction(p,self.root/str(i),self.request)
            text=json.dumps(r)+(self.root/str(i)/'journal.json').read_text()
            self.assertNotIn(secret,text);self.assertEqual(r['failure']['stage'],'install')
            self.assertIn(r['failure']['code'],['unclassified-contract-error','operation-os-error','operation-value-error','operation-timeout'])

    def test_safe_file_json_archive_codes_and_exit_code(self):
        for code in ['file-unavailable','file-type-or-size','invalid-json','archive-path','signed-payload-changed']:
            self.assertEqual(E.failure_details(ContractError(code),'payload-compare')['code'],code)
        def failed(args,timeout):return {'returncode':7,'stdout':'secret','stderr':'password=synthetic'}
        with self.assertRaises(ContractError) as caught:E.official_ok(failed,['fake'])
        self.assertEqual(E.failure_details(caught.exception,'verify-app')['exitCode'],7)
        caught.exception.safe_exit_code='password=synthetic'
        self.assertNotIn('exitCode',E.failure_details(caught.exception,'verify-app'))

    def test_official_command_failures_have_exact_fixed_stage(self):
        for i,(command,stage) in enumerate([('verify-app','verify-app'),('verify-profile','verify-profile'),('ActualSigner','actual-signer')]):
            def run(args,timeout):
                return {'returncode':1,'stdout':'sensitive platform output','stderr':'password=synthetic'} if command in args else self.official(args,timeout)
            with self.assertRaises(ContractError) as caught:
                E.verify_signed(self.unsigned,self.signed,self.config,self.tools,self.root/('stage'+str(i)),run,1000,self.device)
            self.assertEqual(E.failure_details(caught.exception,'install'),{'stage':stage,'code':'official-tool-failed','errorType':'ContractError','exitCode':1})

    def test_cleanup_failure_keeps_safe_stage(self):
        p=Platform(self.binding)
        def cleanup():raise ContractError('cleanup-device-offline')
        p.cleanup=cleanup;r=transaction(p,self.root/'state',self.request)
        self.assertEqual(r['cleanupFailure']['stage'],'cleanup');self.assertEqual(r['cleanupFailure']['code'],'cleanup-device-offline')
        self.assertFalse(r['scenarioPassed'])

    def test_normal_transaction_and_consumed_nonce(self):
        p=Platform(self.binding);r=transaction(p,self.root/'state',self.request)
        self.assertTrue(r['scenarioPassed']);self.assertFalse(r['deviceVerified'])
        self.assertIn('cleanup',p.calls)
        with self.assertRaises(ContractError): transaction(p,self.root/'state',self.request)
    def test_offline_does_not_install(self):
        p=Platform(self.binding);p.online=False;r=transaction(p,self.root/'state',self.request)
        self.assertEqual(r['status'],'pending');self.assertNotIn('install',p.calls)
    def test_unknown_existing_package_not_touched(self):
        p=Platform(self.binding);p.existing=True;r=transaction(p,self.root/'state',self.request)
        self.assertFalse(r['deviceVerified']);self.assertNotIn('install',p.calls);self.assertNotIn('cleanup',p.calls)
    def test_cleanup_unknown_blocks_next_transaction(self):
        p=Platform(self.binding);p.cleanup_valid=False;r=transaction(p,self.root/'state',self.request)
        self.assertFalse(r['scenarioPassed']);self.assertEqual(r['cleanup']['confirmed'],False)
        q=Platform({**self.binding,'nonce':'c'*32})
        with self.assertRaises(ContractError): transaction(q,self.root/'state',{**self.request,'nonce':'c'*32})
        self.assertNotIn('install',q.calls)
    def test_timeout_still_cleans(self):
        p=Platform(self.binding);p.execution_error=True;r=transaction(p,self.root/'state',self.request)
        self.assertFalse(r['scenarioPassed']);self.assertIn('cleanup',p.calls)

    def test_caller_cannot_predeclare_pid(self):
        with self.assertRaises(ContractError): transaction(Platform(self.binding),self.root/'state',self.binding)

    def test_recover_only_same_previous_transaction(self):
        p=Platform(self.binding);p.cleanup_valid=False;transaction(p,self.root/'state',self.request)
        p.cleanup_valid=True;before=p.calls.count('install')
        r=E.recover(p,self.root/'state',self.request)
        self.assertTrue(r['recovered']);self.assertFalse(r['deviceVerified']);self.assertEqual(p.calls.count('install'),before)
    def test_recover_other_nonce_or_offline_is_rejected(self):
        p=Platform(self.binding);p.cleanup_valid=False;transaction(p,self.root/'state',self.request)
        with self.assertRaises(ContractError):E.recover(p,self.root/'state',{**self.request,'nonce':'c'*32})
        p.online=False;r=E.recover(p,self.root/'state',self.request);self.assertFalse(r['recovered'])

class WindowEvidenceTests(unittest.TestCase):
    def test_fixed_app_errors_preserved_unknown_redacted(self):
        binding={'nonce':'a'*32,'bundle':E.BUNDLE,'unsignedHapSHA256':'b'*64}
        for code in ['DIAGNOSTICS_STALE','DIAGNOSTICS_RELEASED','PLAYER_TERMINAL','SESSION_CANCELLED','SESSION_TIMEOUT']:
            rows=E.safe_event_snapshot([dict(binding,event='session-failed',value=code)],binding)
            self.assertEqual(rows['rows'][0]['value'],code)
        self.assertNotIn('private-secret',json.dumps(E.safe_event_snapshot([dict(binding,event='session-failed',value='private-secret')],binding)))
    def test_window_nested_evidence_rebuilt_not_copied(self):
        unsafe={'code':'window-table-incomplete','format':'current25','reportedTotal':4,'observedRows':3,'secret':'private-secret','rowColumnCounts':[25,25],'outputSHA256':'a'*64}
        safe=E.sanitized_cleanup({'windowEvidence':unsafe})['windowEvidence']
        self.assertEqual(safe['code'],'window-table-incomplete');self.assertNotIn('private-secret',json.dumps(safe))
        self.assertEqual(E.safe_window_evidence({'code':'private-secret'})['code'],'window-evidence-unknown')
        for v in [[],{},['private-secret']]:
            self.assertEqual(E.safe_window_evidence({'code':v,'format':v})['code'],'window-evidence-unknown')

if __name__=='__main__': unittest.main()
