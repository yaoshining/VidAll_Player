#!/usr/bin/env python3
"""固定iMac工具/审批/设备语义；不接受任意命令，不把空输出当清理成功。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from controller import ContractError, DeviceLease, digest, is_hash, read_file, read_json, require, verify_artifact, read_zip_members
from executor import BUNDLE, certificate_ders, recover, save_state, transaction, verify_signed

HERE=Path(__file__).resolve().parent
STATE_DIRECTORY=Path('/Users/shiningyao/Library/Application Support/VidAllDeviceExecution/tv-192.168.3.85-5555')

def verify_execution_approval(path,expected_sha,actual,now):
    require(is_hash(expected_sha),'external-execution-approval-required')
    data=read_file(path,262144);require(digest(data)==expected_sha,'execution-approval-digest')
    a=read_json(data)
    fields={'schemaVersion','purpose','nonce','bundleName','deviceSerial','deviceIdSHA256','controllerSHA256','artifactApprovalSHA256','toolLockSHA256','signingConfigSHA256','mode','allowInstall','allowUninstallOwnBundle','expiresAt'}
    require(set(a)==fields and type(a['schemaVersion']) is int and a['schemaVersion']==1,'execution-approval-schema')
    require(a['purpose']=='device-smoke-local' and a['mode']=='normal-local-smoke' and a['bundleName']==BUNDLE,'execution-scope')
    require(a['allowInstall'] is True and a['allowUninstallOwnBundle'] is True and type(a['expiresAt']) is int and now<a['expiresAt'],'execution-not-authorized')
    require(isinstance(a['nonce'],str) and re.fullmatch('[0-9a-f]{32}',a['nonce']),'session-nonce')
    require(a['deviceSerial']=='192.168.3.85:5555' and is_hash(a['deviceIdSHA256']),'approved-device')
    for key in ['controller','artifactApproval','toolLock','signingConfig']:
        require(is_hash(actual.get(key)) and a[key+'SHA256']==actual[key],'execution-input-changed:'+key)
    return a

def command_ok(r):
    return isinstance(r,dict) and type(r.get('returncode')) is int and r['returncode']==0 and not r.get('timedOut') and isinstance(r.get('stdout'),str)

def connected_output(r,serial):
    return command_ok(r) and any(re.fullmatch(re.escape(serial)+r'\s+TCP\s+Connected',line.strip()) for line in r['stdout'].splitlines())

def package_list(r):
    require(command_ok(r),'package-list-failed')
    lines=[line.strip() for line in r['stdout'].splitlines() if line.strip()]
    require(bool(lines) and any(re.fullmatch(r'ID:\s*\d+',line) for line in lines),'package-list-format')
    names=[line for line in lines if not re.fullmatch(r'ID:\s*\d+',line)]
    require(bool(names) and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+',name) for name in names),'package-list-format')
    return names

def package_identity(result,certificate_sha,version):
    require(command_ok(result),'package-query-failed');data=read_json(result['stdout'].encode())
    fingerprint=data.get('signatureInfo',{}).get('fingerprint','').replace(':','').lower()
    require(data.get('name')==BUNDLE and data.get('versionCode')==version and fingerprint==certificate_sha,'installed-package-identity')
    lifecycle=all(type(data.get(k)) is int and data[k]>0 for k in ['installTime','updateTime'])
    return {'passed':True,'bundle':BUNDLE,'versionCode':version,'certificateDER_SHA256':fingerprint,'installationLifecycleVerified':lifecycle,'installTime':data.get('installTime') if lifecycle else None,'updateTime':data.get('updateTime') if lifecycle else None}

def process_identity(pid_result,stat_result):
    require(command_ok(pid_result) and re.fullmatch(r'[1-9][0-9]*\s*',pid_result['stdout']),'pid-query-invalid')
    pid=int(pid_result['stdout']);require(command_ok(stat_result),'process-stat-query-failed')
    value=stat_result['stdout'].strip();require(value.startswith(str(pid)+' (') and ') ' in value,'process-stat-invalid')
    fields=value[value.rfind(') ')+2:].split();require(len(fields)>=20 and fields[19].isdigit() and int(fields[19])>0,'process-start-token')
    return {'pid':pid,'startTicks':int(fields[19])}

def cleanup_proof(records,serial,process=None):
    try:
        require(connected_output(records.get('connection'),serial),'cleanup-device-not-connected')
        for key in ['stop','ability','window','uninstall']:require(command_ok(records.get(key)),'cleanup-command-failed')
        require('force stop process successfully' in records['stop']['stdout'],'stop-semantic-failure')
        pid=records.get('pid',{});require(type(pid.get('returncode')) is int and pid['returncode'] in (0,1) and not pid.get('timedOut') and pid.get('stdout')=='' and not pid.get('stderr'),'process-still-present-or-unknown')
        ability=records['ability']['stdout'];window=records['window']['stdout']
        require(any(s in ability for s in ['AbilityManagerService','current mission lists','AbilityRecord']) and BUNDLE not in ability,'ability-still-present-or-unknown')
        require(any(s in window for s in ['WindowManagerService','Total window num']) and BUNDLE not in window,'window-still-present-or-unknown')
        counts=re.findall(r'^Total window num:\s*(\d+)\s*$',window,re.M);require(len(counts)==1,'window-count-unrecognized')
        if int(counts[0]):
            table=re.search(r'^WindowName\s+WindowId\s+PID\s*\n(.*?)^Total window num:',window,re.M|re.S)
            require(table is not None,'window-format-unrecognized')
            rows=[r for r in table.group(1).splitlines() if r.strip()]
            require(len(rows)==int(counts[0]) and all(re.fullmatch(r'.+\s+[0-9]+\s+[0-9]+\s*',r) for r in rows),'window-table-incomplete')
        if process:
            target=str(process['pid'])
            require(not re.search(r'(?<!\d)'+target+r'(?!\d)',window) and not re.search(r'(?<!\d)'+target+r'(?!\d)',ability),'process-window-or-ability-remains')
        require('uninstall bundle successfully' in records['uninstall']['stdout'] and BUNDLE not in package_list(records.get('packages')),'package-still-present-or-unknown')
        return {'confirmed':True,'appSelfCleanup':'unconfirmed'}
    except (ContractError,KeyError,TypeError,AttributeError):return {'confirmed':False,'appSelfCleanup':'unconfirmed'}

def local_readiness(approval,signing,tools):
    missing=[]
    if approval is None:missing.append('external-execution-approval-missing')
    if signing is None:missing.append('dedicated-signing-material-missing')
    if tools is None:missing.append('approved-device-tools-missing')
    return {'status':'pending','pendingReason':missing or ['actual-signing-and-device-run-required'],'deviceVerified':False,'formalArtifactAllowed':False}

def runtime_tree(root):
    root=Path(root);require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'cli-closure-root')
    entries=[];total=0
    for path in sorted(root.rglob('*')):
        require(len(entries)<20000,'cli-closure-file-limit')
        if path.is_symlink():
            resolved=path.resolve();require(resolved.is_relative_to(root) and resolved.is_file(),'cli-closure-symlink')
            content=read_file(resolved);entries.append({'path':path.relative_to(root).as_posix(),'link':os.readlink(path),'sha256':digest(content)})
        elif path.is_file():
            # node_modules中允许空的package标记文件；read_file对非空输入的规则不适用此清单。
            require(path.stat().st_size<=128*1024*1024,'cli-closure-member-limit');content=path.read_bytes();total+=len(content)
            require(total<512*1024*1024,'cli-closure-byte-limit');entries.append({'path':path.relative_to(root).as_posix(),'sha256':digest(content)})
    return {'files':len(entries),'treeSHA256':digest(json.dumps(entries,sort_keys=True,separators=(',',':')).encode())}

def verify_device_tools(lock,signing):
    require(lock.get('schemaVersion')==1 and lock.get('architecture')=='x86_64' and lock.get('deviceSerial')=='192.168.3.85:5555','device-tools-scope')
    required={'java','signTool','hdc','node','cli'};require(set(lock.get('tools',{}))==required,'device-tools-fields')
    result={}
    for name,item in lock['tools'].items():
        require(set(item)=={'path','sha256'} and Path(item['path']).is_absolute() and is_hash(item['sha256']),'device-tool-entry')
        require(digest(read_file(item['path']))==item['sha256'],'device-tool-changed:'+name);result[name]=item['path']
    closure=lock.get('cliClosure',{});require(isinstance(closure,dict) and Path(result['cli']).is_relative_to(Path(closure.get('packageRoot','/invalid'))),'cli-closure-scope')
    observed=runtime_tree(closure['packageRoot']);require(observed['files']==closure.get('files') and observed['treeSHA256']==closure.get('treeSHA256'),'cli-dependency-closure-changed')
    helper=Path(signing['signerHelperClassPath']);require(helper.is_absolute() and not helper.is_symlink(),'signer-helper-path')
    require(set(p.name for p in helper.iterdir()).issubset({'ActualSigner.class','helper-build.json'}),'signer-helper-extra-code')
    require(digest(read_file(helper/'ActualSigner.class'))==signing['signerHelperClassSHA256'],'signer-helper-changed')
    result['signerHelperClassPath']=str(helper);return result

def verify_invoked_tools(lock,signing,command):
    """仅重核本次实际执行闭包；HDC采样不扫描未用的CLI依赖。"""
    first=str(command[0]);tools=lock['tools']
    if first==tools['hdc']['path']:names=['hdc']
    elif first==tools['node']['path']:
        require(len(command)>1 and str(command[1])==tools['cli']['path'],'unapproved-node-entry');names=['node','cli']
        c=lock['cliClosure'];actual=runtime_tree(c['packageRoot']);require(actual['files']==c['files'] and actual['treeSHA256']==c['treeSHA256'],'cli-dependency-closure-changed')
    elif first==tools['java']['path']:
        names=['java','signTool'];helper=Path(signing['signerHelperClassPath'])
        require(digest(read_file(helper/'ActualSigner.class'))==signing['signerHelperClassSHA256'],'signer-helper-changed')
    else:raise ContractError('unapproved-tool-entry')
    for name in names:require(digest(read_file(tools[name]['path']))==tools[name]['sha256'],'device-tool-changed:'+name)

def controller_identity():
    return digest(b''.join(name.encode()+b'\0'+read_file(HERE/name) for name in ['controller.py','executor.py','imac.py']))

def signing_contract(cfg,approval):
    fields={'schemaVersion','bundleName','deviceIdSHA256','profileFile','profileSHA256','certificateFile','certificateDER_SHA256','keystoreFile','keystoreSHA256','keyAlias','passwordMode','signerHelperClassPath','signerHelperClassSHA256'}
    require(set(cfg)==fields and cfg['schemaVersion']==1 and cfg['bundleName']==BUNDLE and cfg['deviceIdSHA256']==approval['deviceIdSHA256'],'signing-config-scope')
    require(cfg['passwordMode']=='interactive-local' and isinstance(cfg['keyAlias'],str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',cfg['keyAlias']),'signing-mode')
    for key in ['profileSHA256','certificateDER_SHA256','keystoreSHA256','signerHelperClassSHA256']:require(is_hash(cfg[key]),'signing-digest')
    for key in ['profileFile','certificateFile','keystoreFile','signerHelperClassPath']:require(isinstance(cfg[key],str) and Path(cfg[key]).is_absolute(),'signing-path')
    return cfg

def run_command(args,timeout=15):
    """固定调用者提供argv；输出只存本机内存，不自动公开原始设备/材料内容。"""
    child=subprocess.Popen([str(x) for x in args],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        stdout,stderr=child.communicate(timeout=timeout)
        require(len(stdout)+len(stderr)<=2*1024*1024,'command-output-too-large')
        return {'returncode':child.returncode,'stdout':stdout,'stderr':stderr}
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.communicate();raise TimeoutError('command-timeout')

class FixedDevice:
    """固定bundle/设备的窄适配器；所有有副作用方法由外层完整事务锁包围。"""
    def __init__(self,tools,approval,signing,workspace,unsigned,version,*,expected_unsigned_sha,command=run_command):
        self.tools=tools;self.approval=approval;self.signing=signing;self.workspace=Path(workspace)
        require(not self.workspace.exists() and not self.workspace.is_symlink(),'session-directory-reused')
        self.workspace.mkdir(mode=0o700);self.unsigned=Path(unsigned);self.signed=self.workspace/'device-signed.hap'
        require(is_hash(expected_unsigned_sha),'externally-approved-unsigned-required');self.expected_unsigned_sha=expected_unsigned_sha
        self.serial=approval['deviceSerial'];self.nonce=approval['nonce'];self.version=version;self.command=command
        self.verification=None;self.process=None;self.binding=None;self.installed=False;self.app_cleanup=False
        self.installed_identity=None;self.recovering=False
        self.start_clock=0;self.deadline=0;self.device_id=None
        self.collecting=False
        self.tool_guard=lambda:None
    def call(self,args,timeout=15):
        if self.collecting:
            remaining=self.deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('session-timeout')
            timeout=min(timeout,remaining)
        return self.command(args,timeout)
    def hdc(self,args,timeout=15):return self.call([self.tools['hdc'],'-t',self.serial,*args],timeout)
    def connected(self,prefer_cli=True):
        # CLI负责优先盘点；HDC详细状态与真实UDID补齐固定身份，不由TCP地址自证。
        if prefer_cli:
            cli=self.call([self.tools['node'],self.tools['cli'],'device','list'],15)
            if not command_ok(cli) or self.serial not in cli['stdout']:return False
        state=self.call([self.tools['hdc'],'list','targets','-v'],15)
        if not connected_output(state,self.serial):return False
        result=self.hdc(['shell','bm','get','-u']);require(command_ok(result),'device-id-query-failed')
        match=re.fullmatch(r'\s*udid of current device is:\s*([A-Za-z0-9_-]{8,256})\s*',result['stdout']);require(match is not None,'device-id-format')
        self.device_id=match.group(1);require(digest(self.device_id.encode())==self.approval['deviceIdSHA256'],'device-id-mismatch')
        return True
    def package_absent(self):
        require(self.connected(),'device-not-connected');return BUNDLE not in package_list(self.hdc(['shell','bm','dump','-a']))
    def prepare_signed(self):
        require(self.device_id is not None,'fresh-device-required')
        require(digest(read_file(self.unsigned))==self.expected_unsigned_sha,'approved-unsigned-changed')
        cfg=self.signing
        require([digest(d) for d in certificate_ders(read_file(cfg['certificateFile'],1024*1024))].count(cfg['certificateDER_SHA256'])==1,'approved-certificate-file')
        for name,key in [('profileFile','profileSHA256'),('keystoreFile','keystoreSHA256')]:
            p=Path(cfg[name]);require(not p.is_symlink() and p.stat().st_uid==os.geteuid(),'signing-file-owner')
            require(digest(read_file(p,16*1024*1024))==cfg[key],'signing-file-changed')
            if name=='keystoreFile':require(not p.stat().st_mode&0o077,'private-key-permissions')
        # 密码只由官方工具交互终端读取；不接受密码参数/环境值或自动读取旧签名配置。
        require(cfg.get('passwordMode')=='interactive-local' and sys.stdin.isatty() and sys.stdout.isatty(),'interactive-signing-required')
        args=[self.tools['java'],'-jar',self.tools['signTool'],'sign-app','-mode','localSign','-keyAlias',cfg['keyAlias'],'-appCertFile',cfg['certificateFile'],'-profileFile',cfg['profileFile'],'-inFile',str(self.unsigned),'-outFile',str(self.signed),'-keystoreFile',cfg['keystoreFile'],'-signAlg','SHA256withECDSA','-compatibleVersion','15','-pwdInputMode','1']
        # 不capture到CI日志；首阶段仅人工本地受控终端，非交互环境失败关闭。
        self.tool_guard();child=subprocess.Popen(args,start_new_session=True)
        try:require(child.wait(timeout=120)==0,'official-sign-failed')
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait();raise ContractError('official-sign-timeout')
        self.verification=verify_signed(self.unsigned,self.signed,cfg,self.tools,self.workspace/'verify',self.command,int(time.time()),self.device_id)
    def install(self):
        require(digest(read_file(self.unsigned))==self.expected_unsigned_sha,'approved-unsigned-changed')
        require(self.package_absent(),'existing-package-not-owned')
        self.prepare_signed()
        require(self.verification and self.verification.get('signatureVerified') is True,'signature-not-verified')
        require(self.verification.get('unsignedHAP_SHA256')==self.expected_unsigned_sha and digest(read_file(self.unsigned))==self.expected_unsigned_sha,'approved-unsigned-changed')
        require(digest(read_file(self.signed))==self.verification['signedHAP_SHA256'],'signed-package-replaced')
        # 安装前再次看设备/专用bundle，防签名期间被其他来源安装；不用-r覆盖。
        require(self.package_absent(),'existing-package-not-owned')
        result=self.hdc(['install',str(self.signed)],30)
        require(command_ok(result) and 'install bundle successfully' in result['stdout'],'install-semantic-failure')
        self.installed=True
        identity=package_identity(self.hdc(['shell','bm','dump','-n',BUNDLE]),self.signing['certificateDER_SHA256'],self.version)
        self.installed_identity=identity
        require(digest(read_file(self.signed))==self.verification['signedHAP_SHA256'],'signed-package-replaced')
        return {'installedPayloadVerified':True,'packageIdentity':identity}
    def current_process(self):
        result=self.hdc(['shell','pidof',BUNDLE]);require(command_ok(result) and re.fullmatch(r'[1-9][0-9]*\s*',result['stdout']),'pid-query-invalid')
        return process_identity(result,self.hdc(['shell','cat','/proc/'+result['stdout'].strip()+'/stat']))
    def read_events(self):
        path=self.workspace/'events.jsonl'
        if path.exists():path.unlink()
        remote='data/storage/el2/base/haps/entry/files/device-smoke/'+self.nonce+'/events.jsonl'
        r=self.hdc(['file','recv','-b',BUNDLE,remote,str(path)],10)
        if not command_ok(r) or not path.is_file():return []
        data=read_file(path,2*1024*1024);lines=data.splitlines()
        # 传输途中最后一行未换行不作为完成记录。
        if not data.endswith(b'\n'):lines=lines[:-1]
        require(len(lines)<=2048,'too-many-device-events')
        return [read_json(line) for line in lines]
    def start(self):
        require(self.connected(),'device-not-connected')
        current=self.hdc(['shell','pidof',BUNDLE]);require(current.get('returncode') in (0,1) and current.get('stdout')=='' and not current.get('stderr'),'unexpected-preexisting-process')
        clock=self.hdc(['shell','date','+%s']);require(command_ok(clock) and clock['stdout'].strip().isdigit(),'device-clock-unknown');self.start_clock=int(clock['stdout'])*1000
        args=['shell','aa','start','-a','EntryAbility','-b',BUNDLE,'--ps','sessionNonce',self.nonce,'--ps','mode','normal-local-smoke','--ps','expectedUnsignedHapSHA256',self.expected_unsigned_sha]
        launch=self.hdc(args);require(command_ok(launch) and 'start ability successfully' in launch['stdout'],'launch-failed')
        self.deadline=time.monotonic()+120
        while time.monotonic()<self.deadline-110:
            try:
                actual=self.current_process();rows=self.read_events()
                if rows:
                    first=rows[0];clock_now=self.hdc(['shell','date','+%s']);require(command_ok(clock_now) and clock_now['stdout'].strip().isdigit(),'device-clock-unknown')
                    require(first.get('event')=='session-start' and first.get('nonce')==self.nonce and first.get('pid')==actual['pid'],'startup-session-mismatch')
                    started=first.get('startedAtMs');require(type(started) is int and self.start_clock<=started<=int(clock_now['stdout'])*1000+1000,'startup-time-mismatch')
                    require(actual==self.current_process(),'startup-pid-reused');self.process=actual
                    self.binding={'nonce':self.nonce,'bundle':BUNDLE,'unsignedHapSHA256':self.expected_unsigned_sha,'pid':actual['pid'],'startedAtMs':started,'processStartTicks':actual['startTicks']}
                    return self.binding
            except ContractError:
                # 只有尚无日志/尚未出现进程可重试；身份不匹配不能吞掉。
                if 'rows' in locals() and rows:raise
            time.sleep(0.2)
        raise TimeoutError('startup-evidence-missing')
    def collect(self):
        self.collecting=True
        try:
            while time.monotonic()<self.deadline:
                require(self.connected(False) and self.current_process()==self.process,'device-disconnected-or-process-reused')
                rows=self.read_events()
                if time.monotonic()>=self.deadline:raise TimeoutError('session-timeout')
                if rows and rows[-1].get('event') in ('session-end','session-failed'):
                    self.app_cleanup=any(r.get('event')=='keep-screen' and r.get('value')=='false' for r in rows)
                    return rows
                time.sleep(0.5)
            raise TimeoutError('session-timeout')
        finally:self.collecting=False
    def cleanup(self):
        require(self.connected(),'cleanup-device-offline')
        if self.package_absent():
            # 安装前失败时没有应用写入；不得伪造force-stop/uninstall证据。
            require(not self.installed,'installed-package-unexpectedly-absent')
            return {'confirmed':True,'appSelfCleanup':'not-started','deviceMutation':'none'}
        current=package_identity(self.hdc(['shell','bm','dump','-n',BUNDLE]),self.signing['certificateDER_SHA256'],self.version)
        require(self.installed,'install-ownership-unconfirmed')
        require(self.installed_identity is not None and current==self.installed_identity,'installed-lifecycle-changed')
        if self.recovering or self.process is None:require(current['installationLifecycleVerified'],'installation-lifecycle-unconfirmed')
        p=self.hdc(['shell','pidof',BUNDLE])
        require(type(p.get('returncode')) is int and p['returncode'] in (0,1) and not p.get('timedOut') and p.get('stderr')=='' and isinstance(p.get('stdout'),str),'cleanup-prestop-pid-unknown')
        if p['stdout'].strip():require(self.process is not None and self.current_process()==self.process,'cleanup-pid-reused-or-unknown')
        else:require(p['stdout']=='','cleanup-prestop-pid-format')
        records={'stop':self.hdc(['shell','aa','force-stop',BUNDLE])}
        records['pid']=self.hdc(['shell','pidof',BUNDLE]);records['ability']=self.hdc(['shell','aa','dump','-a']);records['window']=self.hdc(['shell','hidumper','-s','WindowManagerService','-a','-a'])
        records['uninstall']=self.hdc(['uninstall',BUNDLE],30);records['packages']=self.hdc(['shell','bm','dump','-a'])
        records['connection']=self.command([self.tools['hdc'],'list','targets','-v'],15)
        result=cleanup_proof(records,self.serial,self.process)
        result['appSelfCleanup']='confirmed' if self.app_cleanup else 'unconfirmed'
        return result

    def restore_identity(self,binding,installed):
        require(installed.get('installedPayloadVerified') is True,'recovery-ownership')
        expected=installed.get('packageIdentity',{})
        require(expected.get('bundle')==BUNDLE and expected.get('versionCode')==self.version and expected.get('certificateDER_SHA256')==self.signing['certificateDER_SHA256'],'recovery-package-mismatch')
        require(expected.get('installationLifecycleVerified') is True,'recovery-installation-lifecycle-unconfirmed')
        self.installed=True;self.binding=binding;self.installed_identity=expected;self.recovering=True
        if binding.get('pid') is not None:
            require(type(binding.get('processStartTicks')) is int,'recovery-process-token-missing')
            self.process={'pid':binding['pid'],'startTicks':binding['processStartTicks']}

def main(argv=None):
    parser=argparse.ArgumentParser(description='专用短测本地入口。默认只报告pending；--execute/--recover须外部精确批准和专用材料。')
    for name in ['artifact','artifact-approval','execution-approval','signing-config','tools-lock','state-directory']:
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--execution-approval-sha256');modes=parser.add_mutually_exclusive_group();modes.add_argument('--execute',action='store_true');modes.add_argument('--recover',action='store_true')
    args=parser.parse_args(argv)
    if not (args.execute or args.recover) or not all([args.artifact,args.artifact_approval,args.execution_approval,args.signing_config,args.tools_lock,args.state_directory,args.execution_approval_sha256]):
        print(json.dumps(local_readiness(args.execution_approval,args.signing_config,args.tools_lock)));return 2
    workspace=None
    try:
        require(os.uname().machine=='x86_64','imac-architecture-mismatch')
        actual={'controller':controller_identity(),'artifactApproval':digest(read_file(args.artifact_approval,262144)),'toolLock':digest(read_file(args.tools_lock,262144)),'signingConfig':digest(read_file(args.signing_config,262144))}
        approval=verify_execution_approval(args.execution_approval,args.execution_approval_sha256,actual,int(time.time()))
        signing=signing_contract(read_json(read_file(args.signing_config,262144)),approval)
        lock=read_json(read_file(args.tools_lock,262144));tools=verify_device_tools(lock,signing)
        result=verify_artifact(args.artifact,args.artifact_approval,approval['artifactApprovalSHA256'])
        require(result['bundleName']==BUNDLE,'dedicated-bundle-required')
        archive=read_file(args.artifact);require(digest(archive)==result['zipSHA256'],'artifact-replaced')
        unsigned=read_zip_members(archive)['device-unsigned.hap'];members=read_zip_members(unsigned);metadata=read_json(members['module.json'])
        module=metadata['module'];require(not module.get('requestPermissions') and not module.get('extensionAbilities'),'device-package-network-or-backup')
        version=metadata['app']['versionCode'];require(type(version) is int and version>0,'package-version')
        if args.execute and (not sys.stdin.isatty() or not sys.stdout.isatty()):
            print(json.dumps({'status':'pending','pendingReason':'interactive-local-signing-required','deviceVerified':False,'formalArtifactAllowed':False}));return 2
        state=args.state_directory;require(state==STATE_DIRECTORY and not state.is_symlink(),'fixed-device-state-directory-required');state.mkdir(mode=0o700,exist_ok=True)
        # 可信控制器/工具校验在任何设备调用和私钥读取之前完成。
        def checked_command(command,timeout):
            require(controller_identity()==actual['controller'],'controller-changed')
            verify_invoked_tools(lock,signing,command)
            return run_command(command,timeout)
        requests={'nonce':approval['nonce'],'bundle':BUNDLE,'unsignedHapSHA256':result['unsignedHAP_SHA256']}
        # workspace仅本轮私有文件；recover使用新本地目录但不生成新的设备会话。
        import tempfile
        workspace=Path(tempfile.mkdtemp(prefix='session-'+approval['nonce']+'-',dir=state));os.chmod(workspace,0o700)
        unsigned_path=workspace/'device-unsigned.hap';unsigned_path.write_bytes(unsigned);os.chmod(unsigned_path,0o600)
        device=FixedDevice(tools,approval,signing,workspace/'private',unsigned_path,version,expected_unsigned_sha=result['unsignedHAP_SHA256'],command=checked_command)
        device.tool_guard=lambda:verify_device_tools(lock,signing)
        report=recover(device,state,requests) if args.recover else transaction(device,state,requests)
        report['deviceVerified']=bool(args.execute and report.get('scenarioPassed'))
        report['controllerSHA256']=actual['controller'];report['approvalSHA256']=args.execution_approval_sha256
        if device.verification:report['signature']=device.verification
        print(json.dumps(report,ensure_ascii=False));return 0 if report.get('deviceVerified') or report.get('recovered') else 2 if report.get('status')=='pending' else 1
    except (ContractError,KeyError,TypeError,ValueError,OSError) as error:
        print(json.dumps({'status':'failed','reason':str(error) if isinstance(error,ContractError) else type(error).__name__,'deviceVerified':False,'formalArtifactAllowed':False}));return 1
    finally:
        # 只删除本进程创建的临时目录；持久journal和用户签名材料始终保留。
        if workspace is not None:
            import shutil
            shutil.rmtree(workspace)

if __name__=='__main__':raise SystemExit(main())
