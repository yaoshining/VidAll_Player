#!/usr/bin/env python3
"""固定本机适配器真实函数测试；没有读取凭据或执行设备命令。"""
import hashlib
import os
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
    def test_observed_package_list_header(self):
        # 实测唯一头是 ID: 100:；包名换成合成数据，不保存其他应用清单。
        for header in ['ID: 0','ID: 100:']:
            self.assertEqual(M.package_list(good(header+'\ncom.synthetic.home\n')),['com.synthetic.home'])

    def test_package_list_rejects_ambiguous_or_error_output(self):
        for raw in ['ID: 100:\nID: 100:\ncom.synthetic.home',
                    'ID: 0\nID: 100:\ncom.synthetic.home',
                    'com.synthetic.home\nID: 100:',
                    'ID: 100::\ncom.synthetic.home',
                    'ID: 100: error\ncom.synthetic.home',
                    'ID: 100:\ncom.synthetic.home\nquery failed',
                    'ID: 100:\n'+BUNDLE+'\n'+BUNDLE,
                    'ID: 100:\n']:
            with self.subTest(raw=raw),self.assertRaises(ContractError):M.package_list(good(raw))
        with self.assertRaises(ContractError):M.package_list({**good('ID: 0\ncom.synthetic.home'),'stderr':'query failed'})

    def test_sign_verify_approval_and_cli_mode_binding(self):
        self.approval.update(purpose='sign-verify-local',mode='sign-verify-only',allowInstall=False,allowUninstallOwnBundle=False);self.write()
        a=self.verify();M.require_action_scope('sign-verify-only',a)
        for action in ['execute','recover']:
            with self.assertRaises(ContractError):M.require_action_scope(action,a)
        for key in ['allowInstall','allowUninstallOwnBundle']:
            self.approval[key]=True;self.write()
            with self.assertRaises(ContractError):self.verify()
            self.approval[key]=False
    def test_sign_verify_device_command_guard(self):
        tools={'hdc':'/approved/hdc','node':'/approved/node','cli':'/approved/cli','java':'/approved/java','signTool':'/approved/sign.jar','signerHelperClassPath':'/approved/helper'}
        for command in [[tools['hdc'],'list','targets','-v'],[tools['hdc'],'-t','192.168.3.85:5555','shell','bm','get','-u'],[tools['hdc'],'-t','192.168.3.85:5555','shell','bm','dump','-a'],[tools['node'],tools['cli'],'device','list']]:M.require_sign_verify_command(command,tools)
        for command in [[tools['hdc'],'install','app.hap'],[tools['hdc'],'uninstall','com.anything'],[tools['hdc'],'-t','192.168.3.85:5555','shell','aa','start'],[tools['node'],tools['cli'],'run'],[tools['hdc'],'-t','other','shell','bm','get','-u']]:
            with self.assertRaises(ContractError):M.require_sign_verify_command(command,tools)

    def observed_package(self):
        # 实机仅保留标题/键结构，身份值全部合成；不是实际已安装probe。
        return {'name':BUNDLE,'versionCode':1000000,'applicationInfo':{'bundleName':BUNDLE,'versionCode':1000000,'name':'Synthetic App','fingerprint':'AB'*32},'installTime':1000,'updateTime':1000}

    def test_observed_package_dump_prefix_and_fingerprint(self):
        raw=BUNDLE+':\n'+json.dumps(self.observed_package())+'\n'
        result=M.package_identity(good(raw),'ab'*32,1000000)
        self.assertTrue(result['passed']);self.assertTrue(result['installationLifecycleVerified'])
        self.assertEqual(result['certificateDER_SHA256'],'ab'*32)

    def test_package_legacy_and_new_sources_must_agree(self):
        data=self.observed_package();data['signatureInfo']={'fingerprint':':'.join(['AB']*32)}
        self.assertTrue(M.package_identity(good(json.dumps(data)),'ab'*32,1000000)['passed'])
        data['signatureInfo']['fingerprint']='cd'*32
        with self.assertRaises(ContractError):M.package_identity(good(json.dumps(data)),'ab'*32,1000000)

    def test_package_dump_wrong_duplicate_or_garbage_prefix(self):
        raw=json.dumps(self.observed_package())
        for value in ['com.other.app:\n'+raw,BUNDLE+':\n'+BUNDLE+':\n'+raw,'error\n'+BUNDLE+':\n'+raw,BUNDLE+': '+raw,BUNDLE+':\n'+raw+'\nextra',raw+'\n'+raw]:
            with self.subTest(value=value),self.assertRaises(ContractError):M.package_identity(good(value),'ab'*32,1000000)

    def test_package_nested_identity_missing_conflict_and_bad_types(self):
        for mutate in [lambda d:d['applicationInfo'].pop('fingerprint'),lambda d:d.update(applicationInfo=[]),lambda d:d['applicationInfo'].update(bundleName='com.other.app'),lambda d:d['applicationInfo'].update(versionCode=2),lambda d:d['applicationInfo'].update(versionCode=True),lambda d:d.update(name='com.other.app'),lambda d:d.update(versionCode=2),lambda d:d.update(versionCode=True),lambda d:d['applicationInfo'].update(fingerprint='cd'*32)]:
            data=self.observed_package();mutate(data)
            with self.subTest(data=data),self.assertRaises(ContractError):M.package_identity(good(BUNDLE+':\n'+json.dumps(data)),'ab'*32,1000000)
        data={'name':BUNDLE,'versionCode':1000000,'signatureInfo':{'fingerprint':'ab'*32},'installTime':1,'updateTime':2}
        with self.assertRaises(ContractError):M.package_identity(good(BUNDLE+':\n'+json.dumps(data)),'ab'*32,1000000)

    def test_package_fingerprint_requires_canonical_encoding(self):
        for value in ['a:b'*32,'a'*63,'a'*65,'ab'*31+':ab','ab'*32+' ',None,123,'GG'*32]:
            data=self.observed_package();data['applicationInfo']['fingerprint']=value
            with self.subTest(value=value),self.assertRaises(ContractError):M.package_identity(good(json.dumps(data)),'ab'*32,1000000)
        data=self.observed_package();data['applicationInfo']['fingerprint']=':'.join(['aB']*32)
        self.assertTrue(M.package_identity(good(BUNDLE+':\n'+json.dumps(data)),'ab'*32,1000000)['passed'])

    def test_package_json_errors_and_command_errors(self):
        raw=BUNDLE+':\n'+json.dumps(self.observed_package())
        for value in [raw.replace('1000000','NaN',1),raw[:-1],raw.replace('"name":','"name":"duplicate","name":',1),BUNDLE+':\n[]']:
            with self.assertRaises(ContractError):M.package_identity(good(value),'ab'*32,1000000)
        for response in [{**good(raw),'stderr':'query failed'},good(raw,2),{**good(raw),'timedOut':True}]:
            with self.assertRaises(ContractError):M.package_identity(response,'ab'*32,1000000)

    def test_package_invalid_or_partial_lifecycle_is_rejected(self):
        for field in ['installTime','updateTime']:
            for value in [0,-1,True,'1000',1.5,None]:
                data=self.observed_package();data[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ContractError):M.package_identity(good(BUNDLE+':\n'+json.dumps(data)),'ab'*32,1000000)
            data=self.observed_package();data.pop(field)
            with self.assertRaises(ContractError):M.package_identity(good(BUNDLE+':\n'+json.dumps(data)),'ab'*32,1000000)
        legacy={'name':BUNDLE,'versionCode':1000000,'signatureInfo':{'fingerprint':'ab'*32},'installTime':0,'updateTime':1}
        with self.assertRaises(ContractError):M.package_identity(good(json.dumps(legacy)),'ab'*32,1000000)

    def test_observed_dump_install_cleanup_real_functions(self):
        d=self.adapter();original=d.command;actions=[]
        def command(args,timeout):
            if args[-4:]==['bm','dump','-n',BUNDLE]:return good(BUNDLE+':\n'+json.dumps(self.observed_package())+'\n')
            if args[-3:]==['shell','pidof',BUNDLE]:return good('',1)
            if args[-3:]==['aa','force-stop',BUNDLE]:actions.append('stop');return self.proof()['stop']
            if args[-3:]==['aa','dump','-a']:return self.proof()['ability']
            if 'WindowManagerService' in args:return self.proof()['window']
            if args[-2:]==['uninstall',BUNDLE]:actions.append('uninstall');self.present=False;return self.proof()['uninstall']
            return original(args,timeout)
        d.command=command
        self.assertTrue(d.install()['installedPayloadVerified']);self.assertTrue(self.present)
        self.assertTrue(d.cleanup()['confirmed']);self.assertFalse(self.present);self.assertEqual(actions,['stop','uninstall'])

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
    def test_cleanup_proof_exposes_exact_failed_checks(self):
        proof=self.proof();proof['stop']=good('failed');proof['window']=good('unknown-window-layout')
        result=M.cleanup_proof(proof,'192.168.3.85:5555')
        self.assertFalse(result['confirmed']);self.assertIn('stop-semantic-failure',result['failedChecks']);self.assertIn('window-evidence-invalid',result['failedChecks'])
        self.assertTrue(result['checks']['uninstall-semantic-success'])

    def test_read_events_persists_safe_snapshot_before_validation(self):
        d=self.adapter();record=M.SmokeEvidence(self.root/'evidence',{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')});d.evidence=record
        row={'schemaVersion':1,'seq':1,'event':'session-failed','cycle':0,'value':'secret-password','elapsedMs':3,'nonce':d.nonce,'bundle':BUNDLE,'pid':4321,'startedAtMs':1000,'unsignedHapSHA256':sha(b'package')}
        def command(args,timeout):
            Path(args[-1]).write_text(json.dumps(row)+'\n');return good('file receive success')
        d.command=command;self.assertEqual(len(d.read_events()),1)
        text=(self.root/'evidence'/('smoke-'+d.nonce+'.json')).read_text();data=json.loads(text)
        self.assertEqual(data['events']['count'],1);self.assertNotIn('secret-password',text)

    def test_window_exact_reason_and_safe_structure(self):
        cases=[('WindowManagerService\nTotal window num: 0','window-header-ambiguous'),
               (self.actual_window().replace('Total window num: 1','Total window num: 2'),'window-table-incomplete'),
               (self.actual_window().replace('SyntheticWindow','secret-window-name'),'ok')]
        for text,code in cases:
            detail=M.window_evidence(good(text),{'pid':4321})
            self.assertEqual(detail['code'],code)
            self.assertNotIn('secret-window-name',json.dumps(detail))
            self.assertIn('reportedTotal',detail)
        huge=M.window_evidence(good('WindowName WindowId PID\nTotal window num: '+'9'*5000))
        self.assertEqual(huge['code'],'window-count-unrecognized');self.assertIsNone(huge['reportedTotal'])
        detail=M.window_evidence({'returncode':1,'stdout':'secret','stderr':'password','timedOut':True})
        self.assertEqual(detail['code'],'window-query-timeout');self.assertNotIn('password',json.dumps(detail))

    def test_window_reason_survives_cleanup_proof(self):
        proof=self.proof();proof['window']=good('WindowManagerService\nTotal window num: 0')
        result=M.cleanup_proof(proof,'192.168.3.85:5555')
        self.assertFalse(result['confirmed']);self.assertEqual(result['windowEvidence']['code'],'window-header-ambiguous')

    def test_cleanup_command_evidence_saved_before_uninstall(self):
        d=self.adapter();d.install();original=d.command
        state=self.root/'evidence';d.evidence=M.SmokeEvidence(state,{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')})
        def command(args,timeout):
            if args[-3:]==['shell','pidof',BUNDLE]:return good('',1)
            if args[-3:]==['aa','force-stop',BUNDLE]:return good('force stop process successfully')
            if args[-3:]==['aa','dump','-a']:return good('AbilityManagerService current mission lists')
            if 'WindowManagerService' in args:return self.proof()['window']
            if args[-2:]==['uninstall',BUNDLE]:
                saved=json.loads((state/('smoke-'+d.nonce+'.json')).read_text())
                self.assertIn('stop',saved['cleanupCommands']);self.assertIn('window',saved['cleanupCommands']);self.assertEqual(saved['cleanupCommands']['window']['windowEvidence']['code'],'ok')
                self.present=False;return good('uninstall bundle successfully')
            return original(args,timeout)
        d.command=command;result=d.cleanup();self.assertTrue(result['confirmed'])
        saved=json.loads((state/('smoke-'+d.nonce+'.json')).read_text());self.assertIn('uninstall',saved['cleanupCommands'])
        self.assertNotIn('force stop process successfully',json.dumps(saved))

    def test_cleanup_timeout_evidence_omits_raw_output(self):
        d=self.adapter();d.install();original=d.command
        d.evidence=M.SmokeEvidence(self.root/'evidence',{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')})
        def command(args,timeout):
            if args[-3:]==['shell','pidof',BUNDLE]:return good('',1)
            if args[-3:]==['aa','force-stop',BUNDLE]:raise TimeoutError('password-secret')
            return original(args,timeout)
        d.command=command
        with self.assertRaises(TimeoutError):d.cleanup()
        text=(self.root/'evidence'/('smoke-'+d.nonce+'.json')).read_text();row=json.loads(text)['cleanupCommands']['stop']
        self.assertTrue(row['timedOut']);self.assertNotIn('password-secret',text);self.assertFalse(any('uninstall' in a for a in self.calls))

    def test_prior_cleanup_semantics_survive_later_timeout(self):
        d=self.adapter();d.install();original=d.command;counter=[0]
        d.evidence=M.SmokeEvidence(self.root/'evidence',{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')})
        def command(args,timeout):
            if args[-3:]==['shell','pidof',BUNDLE]:
                counter[0]+=1
                if counter[0]>1:raise TimeoutError('secret')
                return good('',1)
            if args[-3:]==['aa','force-stop',BUNDLE]:return good('failed secret stop')
            return original(args,timeout)
        d.command=command
        with self.assertRaises(TimeoutError):d.cleanup()
        text=d.evidence.path.read_text();record=json.loads(text)
        self.assertFalse(record['cleanupCommands']['stop']['checks']['stop-semantic-success']);self.assertTrue(record['cleanupCommands']['pid']['timedOut']);self.assertNotIn('secret',text)

    def test_malformed_event_keeps_prior_rows_and_hash_only(self):
        d=self.adapter();d.evidence=M.SmokeEvidence(self.root/'evidence',{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')})
        row={'schemaVersion':1,'seq':1,'event':'session-failed','value':'DIAGNOSTIC_UNAVAILABLE'}
        def command(args,timeout):Path(args[-1]).write_bytes((json.dumps(row)+'\ninvalid-secret\n').encode());return good('received')
        d.command=command
        with self.assertRaises(ContractError):d.read_events()
        text=d.evidence.path.read_text();record=json.loads(text)
        self.assertEqual(record['events']['count'],1);self.assertEqual(record['eventParseFailure']['line'],2);self.assertEqual(record['eventParseFailure']['sha256'],sha(b'invalid-secret'));self.assertNotIn('invalid-secret',text)

    def test_cleanup_evidence_failure_still_attempts_owned_cleanup(self):
        d=self.adapter();d.install();original=d.command
        d.evidence=M.SmokeEvidence(self.root/'evidence',{'nonce':d.nonce,'bundle':BUNDLE,'unsignedHapSHA256':sha(b'package')})
        def command(args,timeout):
            if args[-3:]==['shell','pidof',BUNDLE]:return good('',1)
            if args[-3:]==['aa','force-stop',BUNDLE]:return good('force stop process successfully')
            if args[-3:]==['aa','dump','-a']:return good('AbilityManagerService current mission lists')
            if 'WindowManagerService' in args:return self.proof()['window']
            if args[-2:]==['uninstall',BUNDLE]:self.present=False;return good('uninstall bundle successfully')
            return original(args,timeout)
        d.command=command
        with patch.object(d.evidence,'cleanup_command',side_effect=OSError('disk-secret')):result=d.cleanup()
        self.assertTrue(result['confirmed']);self.assertFalse(self.present);self.assertIn('code',d.evidence_failure)

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

    def test_zero_count_without_header_and_legacy_tail_rejected(self):
        for raw in ['WindowManagerService\nTarget 1 4321\nTotal window num: 0\n','WindowManagerService\nTotal window num: 0\n','WindowManagerService\nWindowName WindowId PID\nother 11 7654\nTotal window num: 1\nunknown tail\n']:
            p=self.proof();p['window']=good(raw)
            self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])

    def actual_window(self,pid=7654):
        # 实机25列及固定附属诊断行；所有窗口名/身份/数值均为合成值。
        header='WindowName DisplayId Pid WinId Type Mode Flag ZOrd Orientation [ x y w h ] [ OffsetX OffsetY ] [ ScaleX ScaleY PivotX PivotY ]'
        row=f'SyntheticWindow 1 {pid} 22 1 1 1 -1 1 [ 1 1 1 1 ] [ 1 1 ] [ 1 1 1.000 1.000 ]'
        return 'WindowManagerService\n'+header+'\n'+row+'\n----------------\nFocus window: 22\nAll Focus window:\nDisplayId: 1 WindowId: 22\nSingleHand: X[0] Y[0] scale[1]\nTotal window num: 1\nHighlighted windows: 0\n'

    def test_real_window_table_cleanup(self):
        p=self.proof();p['window']=good(self.actual_window())
        self.assertTrue(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])
        p['window']=good(self.actual_window(4321))
        self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])

    def test_window_internal_separator_preserves_all_rows(self):
        raw=self.actual_window();second='SyntheticOther 1 4321 23 1 1 1 -1 1 [ 1 1 1 1 ] [ 1 1 ] [ 1 1 1.000 1.000 ]\n'
        raw=raw.replace('Focus window:',second+'Focus window:',1).replace('Total window num: 1','Total window num: 2')
        self.assertEqual(M.window_pids(raw),{7654,4321})
        p=self.proof();p['window']=good(raw)
        self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555',{'pid':4321,'startTicks':123456})['confirmed'])

    def test_real_window_table_rejects_incomplete_or_unknown(self):
        raw=self.actual_window();header=raw.splitlines()[1]
        for bad in [raw.replace('Total window num: 1','Total window num: 2'),raw+'Total window num: 1\n',raw.replace(header,header+'\n'+header),raw.replace(' 7654 ',' bad '),raw.replace(' 7654 ',' 7654 999 '),raw.replace('Pid WinId','WinId Pid'),raw.replace('SyntheticWindow','bad window'),raw.replace('1.000','NaN'),raw.replace('Focus window: 22','Unknown: 22'),raw.replace('Highlighted windows: 0','unexpected'),raw.replace('SyntheticWindow 1 7654 22 1 1 1 -1 1 [ 1 1 1 1 ] [ 1 1 ] [ 1 1 1.000 1.000 ]\n','')]:
            p=self.proof();p['window']=good(bad)
            with self.subTest(bad=bad):self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555')['confirmed'])
        for response in [{**good(raw),'stderr':'query failed'},{**good(raw),'timedOut':True}]:
            p=self.proof();p['window']=response;self.assertFalse(M.cleanup_proof(p,'192.168.3.85:5555')['confirmed'])

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

    def test_real_udid_prompt_whitespace(self):
        d=self.adapter();original=d.command
        # 真实设备仅保留提示格式，标识换成宿主合成值，不保存原UDID。
        for gap in ['',' ','\t',' \t']:
            with self.subTest(gap=repr(gap)):
                d.command=lambda args,timeout: good('udid of current device is'+gap+':\n'+self.device+'\n') if args[-3:]==['bm','get','-u'] else original(args,timeout)
                self.assertTrue(d.connected())

    def test_udid_prompt_does_not_relax_identity_or_errors(self):
        d=self.adapter();original=d.command;valid='udid of current device is :\n'+self.device+'\n'
        responses=[good(valid.replace('current device','another device')),good(valid+'another-id\n'),good('error: '+valid),good(valid.replace(self.device,'A'*7)),good(valid.replace(self.device,'A'*257)),good(valid.replace(self.device,'ABC/DEF123456')),good(valid.replace(self.device,'different_identity')),good(valid,2),{**good(valid),'timedOut':True},{**good('udid of current device is:\n'+self.device),'stderr':'query failed'}]
        for response in responses:
            with self.subTest(response=response):
                d.command=lambda args,timeout: response if args[-3:]==['bm','get','-u'] else original(args,timeout)
                with self.assertRaises(ContractError):d.connected()

    def test_real_hdc_verbose_connection_shape(self):
        serial='192.168.3.85:5555'
        for row in [serial+' TCP Connected',serial+'\t\tTCP\tConnected\tlocalhost\thdc\n']:
            self.assertTrue(M.connected_output(good(row),serial))
        d=self.adapter();original=d.command
        d.command=lambda args,timeout: good(serial+'\t\tTCP\tConnected\tlocalhost\thdc\n') if args[-3:]==['list','targets','-v'] else (good('udid of current device is :\n'+self.device+'\n') if args[-3:]==['bm','get','-u'] else original(args,timeout))
        self.assertTrue(d.connected())

    def test_hdc_connection_duplicates_conflicts_unknown_columns_rejected(self):
        serial='192.168.3.85:5555';normal=serial+' TCP Connected'
        for row in [normal+'\n'+normal,normal+'\n'+serial+' TCP Offline',normal+'\n'+normal+' localhost hdc',normal+' unknown hdc',normal+' localhost other',normal+' localhost hdc extra',serial+' TCP Offline localhost hdc',serial+' TCP Unauthorized localhost hdc','192.168.3.850:5555 TCP Connected']:
            with self.subTest(row=row):self.assertFalse(M.connected_output(good(row),serial))
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
        pages=self.root/'pages-helper';pages.mkdir();(pages/'ExpectedPages.class').write_bytes(b'pages-class')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'bytecode'),'pagesHelperClassPath':str(pages),'pagesHelperClassSHA256':sha(b'pages-class')}
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
        pages=self.root/'pages-helper';pages.mkdir();(pages/'ExpectedPages.class').write_bytes(b'pages-class')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'class'),'pagesHelperClassPath':str(pages),'pagesHelperClassSHA256':sha(b'pages-class')}
        lock={'schemaVersion':1,'architecture':'x86_64','deviceSerial':'192.168.3.85:5555','tools':tools,'cliClosure':{'packageRoot':str(pkg),'files':3,'treeSHA256':sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())}}
        M.verify_device_tools(lock,cfg)
        (pkg/'node_modules/dep/index.js').write_bytes(b'changed but entry unchanged')
        with self.assertRaises(ContractError):M.verify_device_tools(lock,cfg)
    def test_sign_command_pins_official_preprocessing(self):
        d=self.adapter();d.device_id=self.device;d.tools.update({'java':'/approved/java','signTool':'/approved/sign.jar'})
        cert=self.root/'cert.cer';cert.write_bytes(b'public cert')
        profile=self.root/'profile.p7b';profile.write_bytes(b'public profile')
        key=self.root/'key.p12';key.write_bytes(b'synthetic only');key.chmod(0o600)
        d.signing={'certificateFile':str(cert),'certificateDER_SHA256':sha(b'der'),'profileFile':str(profile),'profileSHA256':sha(profile.read_bytes()),'keystoreFile':str(key),'keystoreSHA256':sha(key.read_bytes()),'passwordMode':'interactive-local','keyAlias':'synthetic'}
        d.signed.write_bytes(b'synthetic signed')
        with patch.object(M,'certificate_ders',return_value=[b'der']),patch.object(M.sys.stdin,'isatty',return_value=True),patch.object(M.sys.stdout,'isatty',return_value=True),patch.object(M.subprocess,'Popen') as popen,patch.object(M,'verify_signed',return_value={'signatureVerified':False,'unsignedHAP_SHA256':sha(b'package')}):
            popen.return_value.wait.return_value=0
            M.FixedDevice.prepare_signed(d)
        args=popen.call_args.args[0]
        self.assertNotIn('-a',args);self.assertEqual(args[args.index('-signCode')+1],'1')
        self.assertNotIn('-keyPwd',args);self.assertNotIn('-keystorePwd',args)

    def test_sign_only_refuses_unsigned_changed_during_sign(self):
        d=self.adapter();d.device_id=self.device;d.tools.update({'java':'/approved/java','signTool':'/approved/sign.jar'})
        cert=self.root/'cert.cer';cert.write_bytes(b'public cert')
        profile=self.root/'profile.p7b';profile.write_bytes(b'public profile')
        key=self.root/'key.p12';key.write_bytes(b'synthetic only');key.chmod(0o600)
        d.signing={'certificateFile':str(cert),'certificateDER_SHA256':sha(b'der'),'profileFile':str(profile),'profileSHA256':sha(profile.read_bytes()),'keystoreFile':str(key),'keystoreSHA256':sha(key.read_bytes()),'passwordMode':'interactive-local','keyAlias':'synthetic'}
        d.signed.write_bytes(b'synthetic signed')
        def changed(timeout):d.unsigned.write_bytes(b'replaced');return 0
        with patch.object(M,'certificate_ders',return_value=[b'der']),patch.object(M.sys.stdin,'isatty',return_value=True),patch.object(M.sys.stdout,'isatty',return_value=True),patch.object(M.subprocess,'Popen') as popen,patch.object(M,'verify_signed') as verify:
            popen.return_value.wait.side_effect=changed
            with self.assertRaisesRegex(ContractError,'approved-unsigned-changed'):M.FixedDevice.prepare_signed(d)
            verify.assert_not_called()

    def test_pages_helper_drift_and_readonly_guard(self):
        tools={}
        for name in ['java','signTool']:
            path=self.root/name;path.write_text(name);tools[name]={'path':str(path),'sha256':sha(name.encode())}
        helper=self.root/'helper';helper.mkdir();(helper/'ActualSigner.class').write_bytes(b'class')
        pages=self.root/'pages-helper';pages.mkdir();(pages/'ExpectedPages.class').write_bytes(b'pages')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'class'),'pagesHelperClassPath':str(pages),'pagesHelperClassSHA256':sha(b'pages')}
        lock={'tools':{**tools,'hdc':{'path':'/hdc'},'node':{'path':'/node'}}}
        command=[tools['java']['path'],'-cp',str(pages)+os.pathsep+tools['signTool']['path'],'ExpectedPages','/unsigned','a'*64,'/new-output']
        plain={k:v['path'] for k,v in tools.items()};plain.update({'hdc':'/hdc','node':'/node','cli':'/cli',**{k:cfg[k] for k in ['signerHelperClassPath','pagesHelperClassPath']}})
        M.require_sign_verify_command(command,plain)
        M.verify_invoked_tools(lock,cfg,command)
        (pages/'ExpectedPages.class').write_bytes(b'changed')
        with self.assertRaisesRegex(ContractError,'pages-helper-changed'):M.verify_invoked_tools(lock,cfg,command)

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
        pages=self.root/'pages-helper';pages.mkdir();(pages/'ExpectedPages.class').write_bytes(b'pages-class')
        cfg={'signerHelperClassPath':str(helper),'signerHelperClassSHA256':sha(b'class'),'pagesHelperClassPath':str(pages),'pagesHelperClassSHA256':sha(b'pages-class')}
        lock={'tools':tools,'cliClosure':{'packageRoot':str(self.root),'files':5,'treeSHA256':'a'*64}}
        with patch.object(M,'runtime_tree',return_value={'files':5,'treeSHA256':'a'*64}) as scan:
            for i in range(10):M.verify_invoked_tools(lock,cfg,[str(self.root/'hdc'),'list','targets','-v'])
            M.verify_invoked_tools(lock,cfg,[str(self.root/'java'),'-jar',str(self.root/'signTool')])
            self.assertEqual(scan.call_count,0)
            M.verify_invoked_tools(lock,cfg,[str(self.root/'node'),str(self.root/'cli'),'device','list'])
            self.assertEqual(scan.call_count,1)

if __name__=='__main__':unittest.main()
