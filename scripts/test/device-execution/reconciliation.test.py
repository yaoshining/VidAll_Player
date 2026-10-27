#!/usr/bin/env python3
"""新功能真实函数TDD；合成状态不代表真机验证。"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import reconciliation as R
import imac as M
from executor import safe_command_result
from controller import ContractError, DeviceLease, digest
from executor import BUNDLE

CHECKS=['deviceIdentity','packageAbsent','processAbsent','abilityAbsent','windowAbsent','hostInactive','noSessions']
def encode(value):return (json.dumps(value,sort_keys=True)+'\n').encode()
class Adapter:
    def __init__(self):self.checks={k:True for k in CHECKS};self.calls=0
    def snapshot(self,old):
        self.calls+=1
        return {'checks':self.checks.copy(),'commands':{name:safe_command_result({'returncode':0,'stdout':'','stderr':''}) for name in R.COMMANDS},'observedAt':1000}
class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.state=Path(self.temp.name);os.chmod(self.state,0o700)
        self.old={'status':'cleanup-unknown','binding':{'nonce':'a'*32,'bundle':BUNDLE,'unsignedHapSHA256':'1'*64,'pid':52824},'cleanup':{'confirmed':False},'installed':{'installedPayloadVerified':True}}
        self.raw=encode(self.old);self.ledger=encode({'nonces':['a'*32]})
        (self.state/'journal.json').write_bytes(self.raw);(self.state/'used-nonces.json').write_bytes(self.ledger)
        self.a={'nonce':'b'*32,'oldNonce':'a'*32,'oldJournalSHA256':digest(self.raw),'oldLedgerSHA256':digest(self.ledger),'expiresAt':1100,'issuedAt':900}
        self.device=Adapter()
    def call(self):return R.reconcile(self.state,self.a,'f'*64,self.device,clock=lambda:1000)
    def unchanged(self):
        self.assertEqual((self.state/'journal.json').read_bytes(),self.raw);self.assertEqual((self.state/'used-nonces.json').read_bytes(),self.ledger)
    def test_exact_archive_and_head_only(self):
        result=self.call();self.assertTrue(result['reconciled']);self.assertFalse(result['scenarioPassed'])
        self.assertEqual((self.state/('reconciliation-'+self.a['nonce']+'.original.json')).read_bytes(),self.raw)
        head=json.loads((self.state/'journal.json').read_bytes());self.assertEqual(head['status'],'complete');self.assertFalse(head['cleanup']['confirmed']);self.assertFalse(head['reconciliation']['scenarioPassed'])
        self.assertEqual((self.state/'used-nonces.json').read_bytes(),self.ledger)
    def test_wrong_journal_or_ledger_digest(self):
        for key in ['oldJournalSHA256','oldLedgerSHA256']:
            with self.subTest(key=key):
                old=self.a[key];self.a[key]='0'*64
                with self.assertRaises(ContractError):self.call()
                self.unchanged();self.a[key]=old
    def test_wrong_nonce_or_old_state(self):
        self.a['oldNonce']='c'*32
        with self.assertRaises(ContractError):self.call()
        self.unchanged()
    def test_residual_or_unknown_refuses(self):
        for key in CHECKS:
            with self.subTest(key=key):
                self.device.checks[key]=False
                with self.assertRaises(ContractError):self.call()
                self.unchanged();self.device.checks[key]=True
    def test_expired_before_query(self):
        self.a['expiresAt']=999
        with self.assertRaises(ContractError):self.call()
        self.assertEqual(self.device.calls,0);self.unchanged()
    def test_same_lock_conflict(self):
        with DeviceLease(self.state/'device.lock'):
            with self.assertRaises(ContractError):self.call()
        self.assertEqual(self.device.calls,0);self.unchanged()
    def test_archive_failure_keeps_old(self):
        with patch.object(R,'exclusive_write',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):self.call()
        self.unchanged()
    def test_evidence_failure_keeps_old(self):
        actual=R.exclusive_write
        def write(path,data):
            if str(path).endswith('.evidence.json'):raise OSError('synthetic')
            return actual(path,data)
        with patch.object(R,'exclusive_write',side_effect=write):
            with self.assertRaises(OSError):self.call()
        self.unchanged()
    def test_head_failure_not_reexecuted(self):
        with patch.object(R,'commit_head',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):self.call()
        self.unchanged()
        with self.assertRaises(ContractError):self.call()
        self.unchanged()
    def test_snapshot_interrupted_preserves_head(self):
        self.device.snapshot=lambda old:(_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):self.call()
        self.unchanged()
    def test_cas_ledger_drift_stops(self):
        def changed(old):
            (self.state/'used-nonces.json').write_bytes(encode({'nonces':['a'*32,'c'*32]}))
            return Adapter().snapshot(old)
        self.device.snapshot=changed
        with self.assertRaises(ContractError):self.call()
        self.assertEqual((self.state/'journal.json').read_bytes(),self.raw)
    def test_final_cas_after_evidence_rejects_journal_and_ledger_drift(self):
        original=R.exclusive_write
        for filename in ['journal.json','used-nonces.json']:
            with self.subTest(filename=filename):
                def write(path,data):
                    original(path,data)
                    if str(path).endswith('.head.tmp'):(self.state/filename).write_bytes(b'changed-after-evidence')
                with patch.object(R,'exclusive_write',side_effect=write),self.assertRaises(ContractError):self.call()
                self.assertEqual((self.state/'journal.json').read_bytes(),b'changed-after-evidence' if filename=='journal.json' else self.raw)
                for p in self.state.glob('reconciliation-*'):p.unlink()
                (self.state/'journal.json').write_bytes(self.raw);(self.state/'used-nonces.json').write_bytes(self.ledger)
    def test_no_evidence_secret_injection(self):
        original=self.device.snapshot
        self.device.snapshot=lambda old:{**original(old),'secret':'do-not-persist'}
        with self.assertRaises(ContractError):self.call()
        self.unchanged()
    def test_symlink_or_existing_archive_refuses(self):
        dest=self.state/('reconciliation-'+self.a['nonce']+'.original.json');dest.symlink_to(self.state/'journal.json')
        with self.assertRaises(ContractError):self.call()
        self.unchanged()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.state=Path(self.temp.name)
        self.a={'codeSHA256':R.code_identity(),'stateDirectory':str(self.state),'deviceSerial':'192.168.3.85:5555','deviceIdSHA256':digest(b'SYNTHETIC_UDID_1234'),'ps':{'path':'/bin/ps','sha256':'0'*64}}
        self.lock={'tools':{name:{'path':'/'+name,'sha256':'0'*64} for name in ['hdc','node','cli']},'cliClosure':{}}
        self.calls=[];self.override={}
        self.device=R.ReadOnlyDevice(self.a,self.lock,command=self.command,clock=lambda:1000)
        self.old={'binding':{'pid':52824}}
    def command(self,args,timeout):
        self.calls.append(args);end=args[-1]
        raw=''
        if args[:2]==['/node','/cli']:raw='192.168.3.85:5555 connected'
        elif args[1:]==['list','targets','-v']:raw='192.168.3.85:5555 TCP Connected localhost hdc'
        elif end=='-u':raw='udid of current device is : SYNTHETIC_UDID_1234'
        elif 'bm' in args:raw='ID: 100:\ncom.synthetic.home\n'
        elif 'pidof' in args:raw=''
        elif 'aa' in args:raw='AbilityManagerService\ncurrent mission lists\n'
        elif 'hidumper' in args:raw='WindowManagerService\nWindowName WindowId PID\nTotal window num: 0'
        elif args[0]=='/bin/ps':raw='1 /sbin/launchd\n'
        key='pid' if 'pidof' in args else 'window' if 'hidumper' in args else 'ability' if 'aa' in args else 'host' if args[0]=='/bin/ps' else 'identity' if end=='-u' else 'packages' if 'bm' in args else 'connection' if args[1:]==['list','targets','-v'] else 'cli'
        return self.override.get(key,{'returncode':0,'stdout':raw,'stderr':''})
    def snapshot(self):
        with patch.object(self.device,'guard'):return self.device.snapshot(self.old)
    def test_real_readonly_chain_safe_proof(self):
        proof=self.snapshot();R.safe_proof(proof,999,1000)
        self.assertTrue(all(proof['checks'].values()));self.assertEqual(set(proof['commands']),set(R.COMMANDS))
        self.assertNotIn('SYNTHETIC_UDID',json.dumps(proof));self.assertNotIn('com.synthetic',json.dumps(proof))
    def test_each_residual_or_bad_query(self):
        cases=[('packages','ID: 100:\n'+BUNDLE),('pid','52824'),('ability','AbilityManagerService '+BUNDLE),('window','WindowManagerService\nWindowName WindowId PID\nprobe 1 52824\nTotal window num: 1'),('host','52 /safe/imac.py --execute')]
        for key,value in cases:
            with self.subTest(key=key):
                self.override={key:{'returncode':0,'stdout':value,'stderr':''}}
                with self.assertRaises(ContractError):R.safe_proof(self.snapshot(),999,1000)
        self.override={'pid':{'returncode':2,'stdout':'','stderr':'sensitive error'}}
        with self.assertRaises(ContractError):R.safe_proof(self.snapshot(),999,1000)
    def test_wrong_identity_offline_unknown_windows(self):
        for key,raw in [('identity','udid of current device is : OTHER_DEVICE_123'),('connection','192.168.3.85:5555 TCP Offline'),('window','WindowManagerService unknown')]:
            self.override={key:{'returncode':0,'stdout':raw,'stderr':''}}
            with self.subTest(key=key),self.assertRaises(ContractError):self.snapshot()
    def test_session_residual_and_stale_or_extra_proof(self):
        (self.state/'session-old').mkdir()
        with self.assertRaises(ContractError):R.safe_proof(self.snapshot(),999,1000)
        (self.state/'session-old').rmdir();proof=self.snapshot()
        for p in [{**proof,'observedAt':998},{**proof,'commands':{}},{**proof,'commands':{**proof['commands'],'secret':'secret'}}]:
            with self.assertRaises(ContractError):R.safe_proof(p,999,1000)
    def test_actual_cli_progress_line_only(self):
        self.override={'cli':{'returncode':0,'stdout':'192.168.3.85:5555 connected','stderr':'- Querying connected devices…\n'}}
        R.safe_proof(self.snapshot(),999,1000)
        for stderr in ['- Querying connected devices…\nerror: failed','unknown error','- Querying connected devices…\n- Querying connected devices…\n']:
            self.override['cli']['stderr']=stderr
            with self.assertRaises(ContractError):self.snapshot()
    def test_other_reconciliation_and_execution_wrapper_active(self):
        for command in ['52 /python /trusted/reconciliation.py --execute-reconciliation','53 /bin/bash /private/tmp/vidall-deviceprobe-smoke-round9.command']:
            self.override={'host':{'returncode':0,'stdout':command,'stderr':''}}
            with self.assertRaises(ContractError):R.safe_proof(self.snapshot(),999,1000)
    def test_query_guard_rejects_mutations_before_run(self):
        for cmd in [['/hdc','-t','192.168.3.85:5555','install','app.hap'],['/hdc','-t','192.168.3.85:5555','shell','aa','force-stop',BUNDLE],['/hdc','-t','192.168.3.85:5555','shell','bm','uninstall','-n',BUNDLE],['/java','-jar','sign.jar','sign-app']]:
            with self.assertRaises(ContractError):self.device.call('pid',cmd)
        self.assertEqual(self.calls,[])
    def test_tool_or_source_drift(self):
        with patch.object(R,'code_identity',return_value='1'*64),self.assertRaises(ContractError):self.device.call('connection',['/hdc','list','targets','-v'])
        with patch.object(R,'read_file',return_value=b'changed'),self.assertRaises(ContractError):self.device.call('connection',['/hdc','list','targets','-v'])
        self.assertEqual(self.calls,[])


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tools=b'locked-tools'
        self.a={'schemaVersion':1,'purpose':'cleanup-only-reconciliation','nonce':'b'*32,'oldNonce':'a'*32,'oldJournalSHA256':'1'*64,'oldLedgerSHA256':'2'*64,'codeSHA256':R.code_identity(),'toolsLockSHA256':digest(self.tools),'stateDirectory':str(M.STATE_DIRECTORY),'deviceSerial':'192.168.3.85:5555','deviceIdSHA256':'3'*64,'bundleName':BUNDLE,'issuedAt':900,'expiresAt':1100,'allowDeviceMutation':False,'allowHeadAdvance':True,'python':{'path':'/Library/Developer/CommandLineTools/usr/bin/python3','resolvedPath':str(Path('/Library/Developer/CommandLineTools/usr/bin/python3').resolve()),'sha256':digest(b'host-tool')},'ps':{'path':'/bin/ps','sha256':digest(b'host-tool')},'nextExecutionApprovalSHA256':'4'*64}
    def verify(self):
        data=encode(self.a)
        with patch.object(R,'code_identity',return_value=self.a['codeSHA256']),patch.object(R,'read_file',return_value=b'host-tool'):
            return R.validate_approval(data,digest(data),self.tools,1000)
    def test_approved_exact_scope(self):self.assertEqual(self.verify(),self.a)
    def test_no_approval_or_code_drift(self):
        data=encode(self.a)
        with self.assertRaises(ContractError):R.validate_approval(data,'0'*64,self.tools,1000)
        with patch.object(R,'code_identity',return_value='0'*64),self.assertRaises(ContractError):R.validate_approval(data,digest(data),self.tools,1000)
    def test_schema_target_actions_time_and_nonce(self):
        for key,value in [('allowDeviceMutation',True),('allowHeadAdvance',False),('stateDirectory','/tmp/new-state'),('bundleName','com.other.app'),('deviceSerial','other'),('nonce','a'*32),('expiresAt',999),('expiresAt',999999),('issuedAt',1001),('oldLedgerSHA256','not-a-hash'),('purpose','device-smoke-local')]:
            with self.subTest(key=key,value=value):
                original=self.a[key];self.a[key]=value
                with self.assertRaises(ContractError):self.verify()
                self.a[key]=original
    def test_tool_lock_or_python_drift(self):
        data=encode(self.a)
        with self.assertRaises(ContractError):R.validate_approval(data,digest(data),b'drift',1000)
        with patch.object(R,'read_file',return_value=b'drift'),self.assertRaises(ContractError):R.validate_approval(data,digest(data),self.tools,1000)
    def test_python_symlink_target_drift(self):
        self.a['python']['resolvedPath']='/unapproved/python'
        with self.assertRaises(ContractError):self.verify()
    def test_arbitrary_extra_approval_rejected(self):
        self.a['secret']='sensitive'
        with self.assertRaises(ContractError):self.verify()

if __name__=='__main__':unittest.main()
