#!/usr/bin/env python3
"""固定本机适配器真实函数测试；没有读取凭据或执行设备命令。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
import imac as M
from controller import ContractError
from executor import BUNDLE

def sha(b):return hashlib.sha256(b).hexdigest()
def good(stdout='',code=0):return {'returncode':code,'stdout':stdout,'stderr':''}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.files={}
        for key in ['controller','artifactApproval','toolLock','signingConfig']:
            p=self.root/(key+'.txt');p.write_text(key);self.files[key]=p
        self.approval={'schemaVersion':1,'purpose':'device-smoke-local','nonce':'a'*32,'bundleName':BUNDLE,'deviceSerial':'192.168.3.85:5555','deviceIdSHA256':'b'*64,'controllerSHA256':sha(b'controller'),'artifactApprovalSHA256':sha(b'artifactApproval'),'toolLockSHA256':sha(b'toolLock'),'signingConfigSHA256':sha(b'signingConfig'),'mode':'normal-local-smoke','allowInstall':True,'allowUninstallOwnBundle':True,'expiresAt':1100}
        self.envelope=self.root/'execute.json';self.write()
    def write(self):self.envelope.write_text(json.dumps(self.approval));self.approval_sha=sha(self.envelope.read_bytes())
    def verify(self,now=1000):return M.verify_execution_approval(self.envelope,self.approval_sha,{k:sha(p.read_bytes()) for k,p in self.files.items()},now)
    def test_exact_approval(self):self.assertEqual(self.verify()['nonce'],'a'*32)
    def test_controller_or_tools_changed(self):
        for key in ['controller','toolLock']:
            old=self.files[key].read_bytes();self.files[key].write_bytes(b'changed')
            with self.assertRaises(ContractError):self.verify()
            self.files[key].write_bytes(old)
    def test_wrong_bundle_missing_grant_expired(self):
        for field,value in [('bundleName','com.other.app'),('allowInstall',False),('expiresAt',900)]:
            old=self.approval[field];self.approval[field]=value;self.write()
            with self.assertRaises(ContractError):self.verify()
            self.approval[field]=old
    def test_absent_external_approval(self):
        with self.assertRaises(ContractError):M.verify_execution_approval(self.envelope,'0'*64,{},1000)
    def test_package_identity(self):
        raw=json.dumps({'name':BUNDLE,'versionCode':1000000,'signatureInfo':{'fingerprint':':'.join(['AB']*32)}})
        self.assertTrue(M.package_identity(good(raw),'ab'*32,1000000)['passed'])
        with self.assertRaises(ContractError):M.package_identity(good(raw),'00'*32,1000000)
    def test_actual_pid_and_kernel_start_token(self):
        stat='4321 (app main) S '+' '.join(['0']*18+['123456']+['0']*8)
        r=M.process_identity(good('4321\n'),good(stat));self.assertEqual(r,{'pid':4321,'startTicks':123456})
        with self.assertRaises(ContractError):M.process_identity(good('4321 4322'),good(stat))
    def proof(self):
        return {'connection':good('192.168.3.85:5555 TCP Connected\n'),'stop':good('force stop process successfully'),'pid':good('',1),'ability':good('AbilityManagerService\ncurrent mission lists\n'),'window':good('WindowManagerService\nWindowName WindowId PID\nother 11 7654\nTotal window num: 1\n'),'uninstall':good('uninstall bundle successfully.'),'packages':good('ID: 0\ncom.system.home\n')}
    def test_cleanup_requires_every_success(self):
        self.assertTrue(M.cleanup_proof(self.proof(),'192.168.3.85:5555')['confirmed'])
        for key in self.proof():
            p=self.proof();p[key]=good('',2) if key=='pid' else good('')
            self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555')['confirmed'],key)
    def test_offline_timeout_lingering_package(self):
        for key,value in [('connection',good('192.168.3.85:5555 TCP Offline')),('window',{'timedOut':True}),('packages',good('ID: 0\n'+BUNDLE+'\n')),('ability',good('AbilityManagerService\n'+BUNDLE))]:
            p=self.proof();p[key]=value;self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555')['confirmed'])
    def test_readiness_missing_materials_is_pending(self):
        r=M.local_readiness(None,None,None);self.assertEqual(r['status'],'pending');self.assertFalse(r['deviceVerified'])

    def test_window_owned_pid_without_bundle_is_not_clean(self):
        p=self.proof();p['window']=good('WindowManagerService\nWindowName WindowId PID\nEntryAbility 22 4321\nTotal window num: 1\n')
        self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])

    def test_incomplete_window_table_is_not_clean(self):
        p=self.proof();p['window']=good('WindowManagerService\nWindowName WindowId PID\nTotal window num: 3\n')
        self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])

    def adapter(self):
        self.calls=[];self.device='ABCDEF123456';self.online=True;self.present=False;self.install_ok=True;self.install_timeout=False;self.install_time=1000
        self.tool_paths={'hdc':'/approved/hdc','node':'/approved/node','cli':'/approved/cli.js'}
        def command(args,timeout):
            self.calls.append(args)
            if args[:2]==['/approved/node','/approved/cli.js']:return good('192.168.3.85:5555')
            if args[-3:]==['list','targets','-v']:return good('192.168.3.85:5555 TCP '+('Connected' if self.online else 'Offline'))
            if args[-3:]==['bm','get','-u']:return good('udid of current device is:\n'+self.device)
            if args[-3:]==['bm','dump','-a']:return good('ID: 0\ncom.system.home\n'+(BUNDLE+'\n' if self.present else ''))
            if 'install' in args:
                self.present=True
                if self.install_timeout:raise TimeoutError('install timeout after possible side effect')
                return good('install bundle successfully.' if self.install_ok else 'install failed')
            if args[-4:]==['bm','dump','-n',BUNDLE]:return good(json.dumps({'name':BUNDLE,'versionCode':1000000,'signatureInfo':{'fingerprint':'ab'*32},'installTime':self.install_time,'updateTime':self.install_time}))
            raise AssertionError('未约定命令 '+repr(args))
        a={**self.approval,'deviceIdSHA256':sha(self.device.encode())}
        unsigned=self.root/'unsigned.hap';unsigned.write_bytes(b'package')
        device=M.FixedDevice(self.tool_paths,a,{'certificateDER_SHA256':'ab'*32},self.root/'session',unsigned,1000000,expected_unsigned_sha=sha(b'package'),command=command)
        def prepared():
            device.signed.write_bytes(b'package')
            device.verification={'signatureVerified':True,'signedHAP_SHA256':sha(b'package'),'unsignedHAP_SHA256':sha(b'package')}
        device.prepare_signed=prepared
        return device

    def test_fixed_adapter_connection_and_install(self):
        d=self.adapter();self.assertTrue(d.connected());self.assertTrue(d.package_absent());self.assertTrue(d.install()['installedPayloadVerified'])
        self.assertTrue(all('shell' not in str(a[0]) for a in self.calls))
    def test_signed_replacement_before_install_is_rejected(self):
        d=self.adapter()
        def replaced():
            d.signed.write_bytes(b'changed');d.verification={'signatureVerified':True,'signedHAP_SHA256':sha(b'package')}
        d.prepare_signed=replaced
        with self.assertRaises(ContractError):d.install()
        self.assertFalse(any('install' in a for a in self.calls))

    def test_unsigned_and_signed_replaced_together_are_rejected(self):
        d=self.adapter()
        def changed_pair():
            d.unsigned.write_bytes(b'changed');d.signed.write_bytes(b'changed')
            d.verification={'signatureVerified':True,'signedHAP_SHA256':sha(b'changed'),'unsignedHAP_SHA256':sha(b'changed')}
        d.prepare_signed=changed_pair
        with self.assertRaises(ContractError):d.install()
        self.assertFalse(any('install' in a for a in self.calls))
    def test_install_semantic_failure(self):
        d=self.adapter();self.install_ok=False
        with self.assertRaises(ContractError):d.install()
    def test_existing_bundle_not_overwritten(self):
        d=self.adapter();self.present=True
        with self.assertRaises(ContractError):d.install()
        self.assertFalse(any('install' in a for a in self.calls))

    def test_package_appeared_during_signing_is_not_cleaned(self):
        d=self.adapter();prepare=d.prepare_signed
        def concurrent_install():prepare();self.present=True
        d.prepare_signed=concurrent_install
        with self.assertRaises(ContractError):d.install()
        with self.assertRaises(ContractError):d.cleanup()
        self.assertFalse(any('force-stop' in a or 'uninstall' in a for a in self.calls))
    def test_ambiguous_install_timeout_is_not_cleaned(self):
        d=self.adapter();self.install_timeout=True
        with self.assertRaises(TimeoutError):d.install()
        with self.assertRaises(ContractError):d.cleanup()
        self.assertFalse(any('force-stop' in a or 'uninstall' in a for a in self.calls))

    def test_cleanup_pid_error_is_rejected_before_stop(self):
        d=self.adapter();d.install();d.process={'pid':4321,'startTicks':123456};original=d.hdc
        d.hdc=lambda args,timeout=15: {'returncode':2,'stdout':'','stderr':'query failed'} if args[:2]==['shell','pidof'] else original(args,timeout)
        with self.assertRaises(ContractError):d.cleanup()
        self.assertFalse(any('force-stop' in a or 'uninstall' in a for a in self.calls))
    def test_reinstalled_same_cert_version_is_not_owned(self):
        d=self.adapter();installed=d.install();self.install_time=2000
        d.restore_identity({'nonce':self.approval['nonce'],'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')},installed)
        with self.assertRaises(ContractError):d.cleanup()
        self.assertFalse(any('force-stop' in a or 'uninstall' in a for a in self.calls))

    def test_tools_and_helper_exact_bytes(self):
        names=['java','signTool','hdc','node','cli'];locked={}
        for name in names:
            path=self.root/name;path.write_text(name);locked[name]={'path':str(path),'sha256':sha(name.encode())}
        helper=self.root/'helper';helper.mkdir();(helper/'ActualSigner.class').write_bytes(b'bytecode')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'bytecode')}
        rows=[{'path':p.relative_to(self.root).as_posix(),'sha256':sha(p.read_bytes())} for p in sorted(self.root.rglob('*')) if p.is_file()]
        lock={'schemaVersion':1,'architecture':'x86_64','deviceSerial':'192.168.3.85:5555','tools':locked,'cliClosure':{'packageRoot':str(self.root),'files':len(rows),'treeSHA256':sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())}}
        self.assertEqual(M.verify_device_tools(lock,cfg)['hdc'],str(self.root/'hdc'))
        (self.root/'hdc').write_text('changed')
        with self.assertRaises(ContractError):M.verify_device_tools(lock,cfg)

    def test_cli_transitive_dependency_change_is_rejected(self):
        pkg=self.root/'cli-package';(pkg/'dist').mkdir(parents=True);(pkg/'node_modules/dep').mkdir(parents=True)
        (pkg/'dist/cli.js').write_bytes(b'entry');(pkg/'node_modules/dep/index.js').write_bytes(b'dep');(pkg/'package.json').write_bytes(b'{}')
        rows=[{'path':p.relative_to(pkg).as_posix(),'sha256':sha(p.read_bytes())} for p in sorted(pkg.rglob('*')) if p.is_file()]
        tools={}
        for name in ['java','signTool','hdc','node']:
            p=self.root/name;p.write_text(name);tools[name]={'path':str(p),'sha256':sha(name.encode())}
        tools['cli']={'path':str(pkg/'dist/cli.js'),'sha256':sha(b'entry')}
        helper=self.root/'helper';helper.mkdir();(helper/'ActualSigner.class').write_bytes(b'class')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'class')}
        lock={'schemaVersion':1,'architecture':'x86_64','deviceSerial':'192.168.3.85:5555','tools':tools,'cliClosure':{'packageRoot':str(pkg),'files':3,'treeSHA256':sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())}}
        M.verify_device_tools(lock,cfg)
        (pkg/'node_modules/dep/index.js').write_bytes(b'changed but entry unchanged')
        with self.assertRaises(ContractError):M.verify_device_tools(lock,cfg)
    def test_cli_without_materials_is_pending(self):
        r=subprocess.run([sys.executable,'-B',str(Path(M.__file__))],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,2);self.assertFalse(json.loads(r.stdout)['deviceVerified'])

    def startup_adapter(self):
        d=self.adapter();d.install();base=d.command;self.launched=False;self.start_ticks=123456;self.log_pid=4321
        trace_run=subprocess.run(['node',str(Path(__file__).resolve().parents[1]/'device-package/session.test.cjs'),'--trace-json'],capture_output=True,text=True,timeout=10)
        self.assertEqual(trace_run.returncode,0);trace=json.loads(trace_run.stdout)['events']
        def command(args,timeout):
            if args[-3:]==['date','+%s','unused']:raise AssertionError('不可用格式')
            if args[-3:]==['shell','date','+%s']:return good('1000\n')
            if 'start' in args and 'aa' in args:self.launched=True;return good('start ability successfully.')
            if args[-3:]==['shell','pidof',BUNDLE]:return good('4321\n' if self.launched else '')
            if args[-3:]==['shell','cat','/proc/4321/stat']:return good('4321 (app main) S '+' '.join(['0']*18+[str(self.start_ticks)]+['0']*8))
            if 'recv' in args:
                binding={'nonce':self.approval['nonce'],'bundle':BUNDLE,'pid':self.log_pid,'startedAtMs':1000001,'unsignedHapSHA256':sha(b'package')}
                rows=[{'event':'session-start','cycle':0,'value':'started','elapsedMs':0},*trace]
                Path(args[-1]).write_text(''.join(json.dumps({**binding,**r,'schemaVersion':1,'seq':i})+'\n' for i,r in enumerate(rows,1)))
                return good('FileTransfer finish')
            return base(args,timeout)
        d.command=command;return d
    def test_real_adapter_start_and_shared_trace_collection(self):
        d=self.startup_adapter();binding=d.start();self.assertEqual(binding['pid'],4321);self.assertEqual(binding['processStartTicks'],123456)
        from executor import validate_events
        before=sum(a[:2]==['/approved/node','/approved/cli.js'] for a in self.calls)
        self.assertTrue(validate_events(d.collect(),binding)['passed'])
        after=sum(a[:2]==['/approved/node','/approved/cli.js'] for a in self.calls)
        self.assertEqual(after,before,'采样循环不得重复CLI盘点')
    def test_startup_log_cannot_choose_pid(self):
        d=self.startup_adapter();self.log_pid=999
        with self.assertRaises(ContractError):d.start()
    def test_collect_rejects_pid_reuse(self):
        d=self.startup_adapter();d.start();self.start_ticks=999999
        with self.assertRaises(ContractError):d.collect()
    def test_real_host_command_timeout_is_bounded(self):
        with self.assertRaises(TimeoutError):M.run_command([sys.executable,'-c','import time;time.sleep(2)'],0.02)

    def test_only_cli_calls_rescan_cli_dependency_tree(self):
        tools={}
        for name in ['java','signTool','hdc','node','cli']:
            p=self.root/name;p.write_text(name);tools[name]={'path':str(p),'sha256':sha(name.encode())}
        helper=self.root/'helper';helper.mkdir();(helper/'ActualSigner.class').write_bytes(b'class')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'class')}
        lock={'tools':tools,'cliClosure':{'packageRoot':str(self.root),'files':5,'treeSHA256':'a'*64}}
        with patch.object(M,'runtime_tree',return_value={'files':5,'treeSHA256':'a'*64}) as scan:
            for i in range(10):M.verify_invoked_tools(lock,cfg,[str(self.root/'hdc'),'list','targets','-v'])
            M.verify_invoked_tools(lock,cfg,[str(self.root/'java'),'-jar',str(self.root/'signTool')])
            self.assertEqual(scan.call_count,0)
            M.verify_invoked_tools(lock,cfg,[str(self.root/'node'),str(self.root/'cli'),'device','list'])
            self.assertEqual(scan.call_count,1)

if __name__=='__main__':unittest.main()
