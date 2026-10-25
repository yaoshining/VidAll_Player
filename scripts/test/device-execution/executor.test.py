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
import executor as E
from controller import ContractError, DeviceLease

def encoded(value): return (json.dumps(value, sort_keys=True) + '\n').encode()
def sha(data): return hashlib.sha256(data).hexdigest()
def hap():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z: z.writestr('module.json', b'unchanged')
    return data.getvalue()

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
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.binding = {'nonce': 'a'*32, 'bundle': 'com.yaoshining.vidalldeviceprobe', 'pid': 4321, 'startedAtMs': 1000000, 'unsignedHapSHA256': 'b'*64}
        self.request = {k:self.binding[k] for k in ['nonce','bundle','unsignedHapSHA256']}
        self.unsigned=self.root/'unsigned.hap'; self.signed=self.root/'signed.hap'
        self.unsigned.write_bytes(hap()); self.signed.write_bytes(hap())
        self.cert=b'synthetic certificate DER'; self.pem=b'-----BEGIN CERTIFICATE-----\n'+base64.b64encode(self.cert)+b'\n-----END CERTIFICATE-----\n'
        self.profile=b'synthetic signed profile'; self.device='synthetic-udid'
        self.config={'bundleName':self.binding['bundle'], 'profileSHA256':sha(self.profile), 'certificateDER_SHA256':sha(self.cert), 'deviceIdSHA256':sha(self.device.encode())}
        self.tools={'java':'/approved/java','signTool':'/approved/sign.jar','signerHelperClassPath':'/approved/helper'}
        self.commands=[]; self.missing=False; self.bad_profile=False; self.wrong_cert=False; self.wrong_signer=False
    def official(self, args, timeout):
        self.commands.append(args)
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
    def test_official_verification_and_payload(self):
        result=self.verify(); self.assertTrue(result['signatureVerified']); self.assertTrue(result['payloadEqual'])
        self.assertEqual(len(self.commands),3)

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
    def test_normal_transaction_and_consumed_nonce(self):
        p=Platform(self.binding);r=E.transaction(p,self.root/'state',self.request)
        self.assertTrue(r['scenarioPassed']);self.assertFalse(r['deviceVerified'])
        self.assertIn('cleanup',p.calls)
        with self.assertRaises(ContractError): E.transaction(p,self.root/'state',self.request)
    def test_offline_does_not_install(self):
        p=Platform(self.binding);p.online=False;r=E.transaction(p,self.root/'state',self.request)
        self.assertEqual(r['status'],'pending');self.assertNotIn('install',p.calls)
    def test_unknown_existing_package_not_touched(self):
        p=Platform(self.binding);p.existing=True;r=E.transaction(p,self.root/'state',self.request)
        self.assertFalse(r['deviceVerified']);self.assertNotIn('install',p.calls);self.assertNotIn('cleanup',p.calls)
    def test_cleanup_unknown_blocks_next_transaction(self):
        p=Platform(self.binding);p.cleanup_valid=False;r=E.transaction(p,self.root/'state',self.request)
        self.assertFalse(r['scenarioPassed']);self.assertEqual(r['cleanup']['confirmed'],False)
        q=Platform({**self.binding,'nonce':'c'*32})
        with self.assertRaises(ContractError): E.transaction(q,self.root/'state',{**self.request,'nonce':'c'*32})
        self.assertNotIn('install',q.calls)
    def test_timeout_still_cleans(self):
        p=Platform(self.binding);p.execution_error=True;r=E.transaction(p,self.root/'state',self.request)
        self.assertFalse(r['scenarioPassed']);self.assertIn('cleanup',p.calls)

    def test_caller_cannot_predeclare_pid(self):
        with self.assertRaises(ContractError): E.transaction(Platform(self.binding),self.root/'state',self.binding)

    def test_recover_only_same_previous_transaction(self):
        p=Platform(self.binding);p.cleanup_valid=False;E.transaction(p,self.root/'state',self.request)
        p.cleanup_valid=True;before=p.calls.count('install')
        r=E.recover(p,self.root/'state',self.request)
        self.assertTrue(r['recovered']);self.assertFalse(r['deviceVerified']);self.assertEqual(p.calls.count('install'),before)
    def test_recover_other_nonce_or_offline_is_rejected(self):
        p=Platform(self.binding);p.cleanup_valid=False;E.transaction(p,self.root/'state',self.request)
        with self.assertRaises(ContractError):E.recover(p,self.root/'state',{**self.request,'nonce':'c'*32})
        p.online=False;r=E.recover(p,self.root/'state',self.request);self.assertFalse(r['recovered'])

if __name__=='__main__': unittest.main()
