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
from executor import BUNDLE, certificate_ders, recover, save_state, transaction, verify_signed, sign_verify_transaction, failure_details, SmokeEvidence, safe_window_evidence, WINDOW_CODES

HERE=Path(__file__).resolve().parent
STATE_DIRECTORY=Path('/Users/shiningyao/Library/Application Support/VidAllDeviceExecution/tv-192.168.3.85-5555')

def verify_execution_approval(path,expected_sha,actual,now):
    require(is_hash(expected_sha),'external-execution-approval-required')
    data=read_file(path,262144);require(digest(data)==expected_sha,'execution-approval-digest')
    a=read_json(data)
    fields={'schemaVersion','purpose','nonce','bundleName','deviceSerial','deviceIdSHA256','controllerSHA256','artifactApprovalSHA256','toolLockSHA256','signingConfigSHA256','mode','allowInstall','allowUninstallOwnBundle','expiresAt'}
    require(set(a)==fields and type(a['schemaVersion']) is int and a['schemaVersion']==1,'execution-approval-schema')
    smoke=a['purpose']=='device-smoke-local' and a['mode']=='normal-local-smoke' and a['allowInstall'] is True and a['allowUninstallOwnBundle'] is True
    verify=a['purpose']=='sign-verify-local' and a['mode']=='sign-verify-only' and a['allowInstall'] is False and a['allowUninstallOwnBundle'] is False
    require((smoke or verify) and a['bundleName']==BUNDLE,'execution-scope')
    require(type(a['expiresAt']) is int and now<a['expiresAt'],'execution-not-authorized')
    require(isinstance(a['nonce'],str) and re.fullmatch('[0-9a-f]{32}',a['nonce']),'session-nonce')
    require(a['deviceSerial']=='192.168.3.85:5555' and is_hash(a['deviceIdSHA256']),'approved-device')
    for key in ['controller','artifactApproval','toolLock','signingConfig']:
        require(is_hash(actual.get(key)) and a[key+'SHA256']==actual[key],'execution-input-changed:'+key)
    return a

def require_action_scope(action,approval):
    expected='sign-verify-only' if action=='sign-verify-only' else 'normal-local-smoke' if action in ('execute','recover') else None
    require(expected is not None and approval['mode']==expected,'execution-mode-mismatch')

def require_sign_verify_command(command,tools):
    """第二层门禁：诊断分支即使误接旧方法也不能调用安装/启动/清理命令。"""
    c=[str(x) for x in command];h=tools['hdc'];serial='192.168.3.85:5555'
    allowed=[[h,'list','targets','-v'],[h,'-t',serial,'shell','bm','get','-u'],[h,'-t',serial,'shell','bm','dump','-a'],[tools['node'],tools['cli'],'device','list']]
    java=(len(c)>=4 and c[:3]==[tools['java'],'-jar',tools['signTool']] and c[3] in ('verify-app','verify-profile'))
    helper=(len(c)==7 and c[:4]==[tools['java'],'-cp',tools['signerHelperClassPath']+os.pathsep+tools['signTool'],'ActualSigner'])
    pages=(len(c)==7 and c[:4]==[tools['java'],'-cp',tools.get('pagesHelperClassPath','/unapproved')+os.pathsep+tools['signTool'],'ExpectedPages'])
    require(c in allowed or java or helper or pages,'sign-verify-command-denied')

def command_ok(r):
    return isinstance(r,dict) and type(r.get('returncode')) is int and r['returncode']==0 and not r.get('timedOut') and isinstance(r.get('stdout'),str)

def connected_output(r,serial):
    if not command_ok(r) or r.get('stderr'):return False
    # 只兼容旧三列及实测五列；同一目标重复/冲突或未知尾列都不能自选健康行。
    targets=[parts for line in r['stdout'].splitlines() if (parts:=line.split()) and parts[0]==serial]
    return len(targets)==1 and targets[0] in ([serial,'TCP','Connected'],[serial,'TCP','Connected','localhost','hdc'])

def package_list(r):
    require(command_ok(r) and not r.get('stderr'),'package-list-failed')
    lines=[line.strip() for line in r['stdout'].splitlines() if line.strip()]
    # 仅兼容实测末尾冒号和旧格式；唯一头必须在首行，多用户/混合输出不自选。
    require(bool(lines) and re.fullmatch(r'ID:[ \t]*[0-9]+:?',lines[0]),'package-list-format')
    names=lines[1:]
    require(bool(names) and len(names)==len(set(names)) and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+',name) for name in names),'package-list-format')
    return names

def package_identity(result,certificate_sha,version):
    require(command_ok(result) and not result.get('stderr'),'package-query-failed')
    # 仅剥离实测的精确专用包标题；错误/重复标题或前后垃圾仍由严格JSON拒绝。
    raw=result['stdout'];prefix=BUNDLE+':\n';prefixed=raw.startswith(prefix)
    data=read_json((raw[len(prefix):] if prefixed else raw).encode())
    require(data.get('name')==BUNDLE and type(data.get('versionCode')) is int and data['versionCode']==version,'installed-package-identity')
    fingerprints=[]
    if 'applicationInfo' in data:
        app=data['applicationInfo'];require(isinstance(app,dict),'installed-package-identity')
        if 'bundleName' in app:require(app['bundleName']==BUNDLE,'installed-package-identity')
        if 'versionCode' in app:require(type(app['versionCode']) is int and app['versionCode']==version,'installed-package-identity')
        fingerprints.append(app.get('fingerprint'))
    else:require(not prefixed,'installed-package-identity')
    if 'signatureInfo' in data:
        legacy=data['signatureInfo'];require(isinstance(legacy,dict),'installed-package-identity');fingerprints.append(legacy.get('fingerprint'))
    require(bool(fingerprints),'installed-package-identity')
    normalized=[]
    for fingerprint in fingerprints:
        require(isinstance(fingerprint,str) and re.fullmatch(r'(?:[0-9A-Fa-f]{64}|(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2})',fingerprint),'installed-package-identity')
        normalized.append(fingerprint.replace(':','').lower())
    require(all(value==certificate_sha for value in normalized),'installed-package-identity')
    lifecycle=all(type(data.get(k)) is int and data[k]>0 for k in ['installTime','updateTime'])
    # 旧无生命周期的纯JSON仍只作身份匹配；实际格式及显式字段必须完整合法，不能降级掩盖损坏。
    if prefixed or 'applicationInfo' in data or any(k in data for k in ['installTime','updateTime']):require(lifecycle,'installed-package-identity')
    return {'passed':True,'bundle':BUNDLE,'versionCode':version,'certificateDER_SHA256':normalized[0],'installationLifecycleVerified':lifecycle,'installTime':data.get('installTime') if lifecycle else None,'updateTime':data.get('updateTime') if lifecycle else None}

def process_identity(pid_result,stat_result):
    require(command_ok(pid_result) and re.fullmatch(r'[1-9][0-9]*\s*',pid_result['stdout']),'pid-query-invalid')
    pid=int(pid_result['stdout']);require(command_ok(stat_result),'process-stat-query-failed')
    value=stat_result['stdout'].strip();require(value.startswith(str(pid)+' (') and ') ' in value,'process-stat-invalid')
    fields=value[value.rfind(') ')+2:].split();require(len(fields)>=20 and fields[19].isdigit() and int(fields[19])>0,'process-start-token')
    return {'pid':pid,'startTicks':int(fields[19])}

def window_pids(output):
    """只认旧三列或实测25列；未知布局不能作为窗口已退出的证据。"""
    lines=[line.strip() for line in output.splitlines() if line.strip()]
    totals=[i for i,line in enumerate(lines) if re.fullmatch(r'Total window num:[ \t]*[0-9]+',line)]
    require(len(totals)==1,'window-count-unrecognized');end=totals[0];count=int(lines[end].split(':')[1])
    headers=[i for i,line in enumerate(lines) if line.startswith('WindowName')]
    require(len(headers)==1 and headers[0]<end,'window-header-ambiguous');start=headers[0]
    header=lines[start].split();body=lines[start+1:end]
    current='WindowName DisplayId Pid WinId Type Mode Flag ZOrd Orientation [ x y w h ] [ OffsetX OffsetY ] [ ScaleX ScaleY PivotX PivotY ]'.split()
    if header==['WindowName','WindowId','PID']:
        require(len(body)==count and end==len(lines)-1,'window-table-incomplete')
        require(all(re.fullmatch(r'\S+[ \t]+[0-9]+[ \t]+[0-9]+',line) for line in body),'window-row-unrecognized')
        return {int(line.split()[2]) for line in body}
    require(header==current,'window-format-unrecognized')
    separators=[i for i,line in enumerate(body) if re.fullmatch(r'-+',line)]
    require(len(separators)==1,'window-separator-unrecognized')
    focus=[i for i,line in enumerate(body) if line.startswith('Focus window:')]
    require(len(focus)==1 and separators[0]<focus[0],'window-section-unrecognized');cut=focus[0]
    rows=[line for i,line in enumerate(body[:cut]) if i!=separators[0]];tail=body[cut:]
    require(len(rows)==count,'window-table-incomplete')
    number=r'-?[0-9]+(?:\.[0-9]+)?'
    require(len(tail)==4 and re.fullmatch(r'Focus window: -?[0-9]+',tail[0]) and tail[1]=='All Focus window:' and re.fullmatch(r'DisplayId: [0-9]+ WindowId: -?[0-9]+',tail[2]) and re.fullmatch(r'SingleHand: X\['+number+r'\] Y\['+number+r'\] scale\['+number+r'\]',tail[3]),'window-metadata-unrecognized')
    require(len(lines[end+1:])==1 and re.fullmatch(r'Highlighted windows: [0-9]+',lines[end+1]),'window-tail-unrecognized')
    pids=set();windows=set()
    for line in rows:
        cells=line.split();require(len(cells)==25,'window-row-unrecognized')
        require(all(re.fullmatch(r'-?[0-9]+',cells[i]) for i in list(range(1,9))+list(range(10,14))),'window-integer-field')
        require(all(re.fullmatch(number,cells[i]) for i in [16,17,20,21,22,23]),'window-number-field')
        require([cells[i] for i in [9,14,15,18,19,24]]==['[',']','[',']','[',']'],'window-row-brackets')
        require(int(cells[2])>=0 and int(cells[3])>=0 and cells[3] not in windows,'window-identity-field')
        windows.add(cells[3]);pids.add(int(cells[2]))
    return pids

def window_evidence(response,process=None):
    """只留固定结构与摘要；不保存窗口名、其他应用或命令原文。接受规则仍由window_pids决定。"""
    response=response if isinstance(response,dict) else {}
    text=response.get('stdout');detail={'code':'window-output-invalid','parsePassed':False,'commandPassed':False,'absenceConfirmed':False}
    if isinstance(text,str) and len(text.encode())<=2*1024*1024:
        raw=text.encode();lines=[x.strip() for x in text.splitlines() if x.strip()]
        headers=[i for i,x in enumerate(lines) if x.startswith('WindowName')]
        totals=[i for i,x in enumerate(lines) if re.fullmatch(r'Total window num:[ \t]*[0-9]+',x)]
        focus=[i for i,x in enumerate(lines) if x.startswith('Focus window:')]
        detail.update(outputBytes=len(raw),outputSHA256=digest(raw),headerCount=len(headers),totalCount=len(totals),focusCount=len(focus),separatorCount=sum(bool(re.fullmatch('-+',x)) for x in lines),reportedTotal=None,observedRows=None)
        if len(totals)==1:
            digits=lines[totals[0]].split(':')[1].strip()
            if len(digits)<=7:detail['reportedTotal']=int(digits)
        if len(headers)==1:
            header=lines[headers[0]].split();detail['format']='legacy3' if header==['WindowName','WindowId','PID'] else ('current25' if len(header)==25 else 'unknown')
            end=focus[0] if len(focus)==1 else (totals[0] if len(totals)==1 else None)
            if end is not None and end>headers[0]:
                rows=[x for x in lines[headers[0]+1:end] if not re.fullmatch('-+',x)]
                detail.update(observedRows=len(rows),rowColumnCounts=[len(x.split()) for x in rows[:64]],rowsTruncated=len(rows)>64)
        try:
            require(len(totals)!=1 or len(lines[totals[0]].split(':')[1].strip())<=7,'window-count-unrecognized')
            pids=window_pids(text);detail['parsePassed']=True;detail['bundleMentioned']=BUNDLE in text
            detail['targetProcessMentioned']=bool(process and process['pid'] in pids)
            detail['code']='window-bundle-present' if detail['bundleMentioned'] else ('window-process-present' if detail['targetProcessMentioned'] else 'ok')
        except (ContractError,KeyError,TypeError,ValueError) as error:
            detail['code']=str(error) if str(error) in WINDOW_CODES else 'window-evidence-unknown'
    detail['commandPassed']=command_ok(response) and not bool(response.get('stderr'))
    if response.get('timedOut'):detail['code']='window-query-timeout'
    elif not detail['commandPassed']:detail['code']='window-query-failed'
    detail['absenceConfirmed']=detail['code']=='ok' and detail['parsePassed'] and detail['commandPassed']
    return safe_window_evidence(detail)

def window_resample_allowed(response,process):
    # 只决定是否允许再查询，绝不把修正计数后的副本作为通过证据。
    detail=window_evidence(response,process)
    if not detail['commandPassed'] or detail['code']!='window-table-incomplete':return False
    raw=response['stdout']
    if BUNDLE in raw or detail.get('observedRows') is None or detail.get('reportedTotal')==detail['observedRows']:return False
    try:
        # 计数失配可能掩盖坏行/重复ID/目标窗口；仍用原严格解析验证完整行结构。
        structural=re.sub(r'(?m)^([ \t]*Total window num:[ \t]*)[0-9]+[ \t]*$',lambda m:m[1]+str(detail['observedRows']),raw)
        pids=window_pids(structural)
        return process is not None and process['pid'] not in pids
    except (ContractError,ValueError,KeyError,TypeError):return False

def cleanup_proof(records,serial,process=None):
    # 各项保持原严格判定，但不再吞掉具体哪项证据失效。
    checks={};failed=[]
    def check(name,reason,call):
        try:passed=call() is True
        except (ContractError,KeyError,TypeError,AttributeError,ValueError):passed=False
        checks[name]=passed
        if not passed:failed.append(reason)
    check('device-connected','cleanup-device-not-connected',lambda:connected_output(records.get('connection'),serial))
    for key in ['stop','ability','window','uninstall']:
        check(key+'-command-success',key+'-command-failed',lambda key=key:command_ok(records.get(key)) and not bool(records[key].get('stderr')))
    check('stop-semantic-success','stop-semantic-failure',lambda:'force stop process successfully' in records['stop']['stdout'])
    def pid_absent():
        pid=records.get('pid',{})
        return type(pid.get('returncode')) is int and pid['returncode'] in (0,1) and not pid.get('timedOut') and pid.get('stdout')=='' and not pid.get('stderr')
    check('pid-absent','process-still-present-or-unknown',pid_absent)
    def ability_absent():
        text=records['ability']['stdout']
        return any(v in text for v in ['AbilityManagerService','current mission lists','AbilityRecord']) and BUNDLE not in text and (not process or not re.search(r'(?<!\d)'+str(process['pid'])+r'(?!\d)',text))
    check('ability-absent','ability-still-present-or-unknown',lambda:bool(ability_absent()))
    def window_absent():
        text=records['window']['stdout'];pids=window_pids(text)
        return any(v in text for v in ['WindowManagerService','Total window num']) and BUNDLE not in text and (not process or process['pid'] not in pids)
    check('window-absent','window-evidence-invalid',lambda:bool(window_absent()))
    check('uninstall-semantic-success','uninstall-semantic-failure',lambda:'uninstall bundle successfully' in records['uninstall']['stdout'])
    check('package-absent','package-still-present-or-unknown',lambda:BUNDLE not in package_list(records.get('packages')))
    return {'confirmed':all(checks.values()),'appSelfCleanup':'unconfirmed','checks':checks,'failedChecks':failed,'windowEvidence':window_evidence(records.get('window'),process)}

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
    result['signerHelperClassPath']=str(helper)
    pages=Path(signing['pagesHelperClassPath']);require(pages.is_absolute() and not pages.is_symlink(),'pages-helper-path')
    require(set(p.name for p in pages.iterdir()).issubset({'ExpectedPages.class','helper-build.json'}),'pages-helper-extra-code')
    require(digest(read_file(pages/'ExpectedPages.class'))==signing['pagesHelperClassSHA256'],'pages-helper-changed')
    result['pagesHelperClassPath']=str(pages);return result

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
        require(digest(read_file(Path(signing['pagesHelperClassPath'])/'ExpectedPages.class'))==signing['pagesHelperClassSHA256'],'pages-helper-changed')
    else:raise ContractError('unapproved-tool-entry')
    for name in names:require(digest(read_file(tools[name]['path']))==tools[name]['sha256'],'device-tool-changed:'+name)

def controller_identity():
    return digest(b''.join(name.encode()+b'\0'+read_file(HERE/name) for name in ['controller.py','executor.py','imac.py']))

def signing_contract(cfg,approval):
    fields={'schemaVersion','bundleName','deviceIdSHA256','profileFile','profileSHA256','certificateFile','certificateDER_SHA256','keystoreFile','keystoreSHA256','keyAlias','passwordMode','signerHelperClassPath','signerHelperClassSHA256','pagesHelperClassPath','pagesHelperClassSHA256','pagesInfoSHA256','pagesInfoBytes'}
    require(set(cfg)==fields and cfg['schemaVersion']==1 and cfg['bundleName']==BUNDLE and cfg['deviceIdSHA256']==approval['deviceIdSHA256'],'signing-config-scope')
    require(cfg['passwordMode']=='interactive-local' and isinstance(cfg['keyAlias'],str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',cfg['keyAlias']),'signing-mode')
    for key in ['profileSHA256','certificateDER_SHA256','keystoreSHA256','signerHelperClassSHA256','pagesHelperClassSHA256','pagesInfoSHA256']:require(is_hash(cfg[key]),'signing-digest')
    for key in ['profileFile','certificateFile','keystoreFile','signerHelperClassPath','pagesHelperClassPath']:require(isinstance(cfg[key],str) and Path(cfg[key]).is_absolute(),'signing-path')
    require(type(cfg['pagesInfoBytes']) is int and 0<cfg['pagesInfoBytes']<=1024*1024,'signing-pages-size')
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
        result=self.hdc(['shell','bm','get','-u']);require(command_ok(result) and not result.get('stderr'),'device-id-query-failed')
        match=re.fullmatch(r'\s*udid of current device is[ \t]*:\s*([A-Za-z0-9_-]{8,256})\s*',result['stdout']);require(match is not None,'device-id-format')
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
        args=[self.tools['java'],'-jar',self.tools['signTool'],'sign-app','-mode','localSign','-keyAlias',cfg['keyAlias'],'-appCertFile',cfg['certificateFile'],'-profileFile',cfg['profileFile'],'-inFile',str(self.unsigned),'-outFile',str(self.signed),'-keystoreFile',cfg['keystoreFile'],'-signAlg','SHA256withECDSA','-compatibleVersion','15','-signCode','1','-pwdInputMode','1']
        # 不capture到CI日志；首阶段仅人工本地受控终端，非交互环境失败关闭。
        self.tool_guard();child=subprocess.Popen(args,start_new_session=True)
        try:require(child.wait(timeout=120)==0,'official-sign-failed')
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait();raise ContractError('official-sign-timeout')
        signed_data=read_file(self.signed);self.signed_identity={'sha256':digest(signed_data),'bytes':len(signed_data)}
        require(digest(read_file(self.unsigned))==self.expected_unsigned_sha,'approved-unsigned-changed')
        self.verification=verify_signed(self.unsigned,self.signed,cfg,self.tools,self.workspace/'verify',self.command,int(time.time()),self.device_id)
        require(self.verification.get('unsignedHAP_SHA256')==self.expected_unsigned_sha and digest(read_file(self.unsigned))==self.expected_unsigned_sha,'approved-unsigned-changed')
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
        path=self.workspace/'events.jsonl';evidence=getattr(self,'evidence',None)
        try:
            if path.exists():path.unlink()
            remote='data/storage/el2/base/haps/entry/files/device-smoke/'+self.nonce+'/events.jsonl'
            r=self.hdc(['file','recv','-b',BUNDLE,remote,str(path)],10)
            if evidence:evidence.event_read(r)
            if not command_ok(r) or not path.is_file():return []
            data=read_file(path,2*1024*1024);lines=data.splitlines()
            if not data.endswith(b'\n'):lines=lines[:-1]
            require(len(lines)<=2048,'too-many-device-events')
            rows=[]
            for index,line in enumerate(lines,1):
                try:rows.append(read_json(line))
                except (ContractError,ValueError):
                    if evidence:
                        evidence.events(rows,getattr(self,'binding',None) or evidence.binding);evidence.parse_failure(index,line)
                    raise
            # 每次成功采样即保存白名单快照，先于场景校验、下一命令与卸载。
            if evidence:evidence.events(rows,getattr(self,'binding',None) or evidence.binding)
            return rows
        except (ContractError,TimeoutError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:
            error.safe_stage='read-events'
            if evidence:
                try:evidence.event_read(error=error);evidence.checkpoint('read-events',error)
                except (ContractError,OSError,ValueError,KeyboardInterrupt,SystemExit) as recording_error:self.evidence_failure=failure_details(recording_error,'read-events')
            raise
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
        evidence=getattr(self,'evidence',None);phase='pre-uninstall'
        def observe(name,call):
            try:value=call()
            except (ContractError,TimeoutError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:
                if evidence:
                    try:evidence.cleanup_command(name,error=error,phase=phase,window=window_evidence({'timedOut':isinstance(error,TimeoutError)},self.process) if name=='window' else None)
                    except (ContractError,OSError,ValueError,KeyboardInterrupt,SystemExit) as recording_error:self.evidence_failure=failure_details(recording_error,'cleanup')
                raise
            if evidence:
                try:
                    keys={'identity':[],'prestop-pid':[],'stop':['stop-command-success','stop-semantic-success'],
                        'pid':['pid-absent'],'ability':['ability-command-success','ability-absent'],
                        'window':['window-command-success','window-absent'],'uninstall':['uninstall-command-success','uninstall-semantic-success'],
                        'packages':['package-absent'],'connection':['device-connected']}.get(name,[])
                    checked=cleanup_proof({name:value},self.serial,self.process)['checks']
                    evidence.cleanup_command(name,value,phase=phase,checks={k:checked[k] for k in keys},window=window_evidence(value,self.process) if name=='window' else None)
                except (ContractError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:self.evidence_failure=failure_details(error,'cleanup')
            return value
        def ownership(**values):
            if evidence:
                try:evidence.ownership(**values)
                except (ContractError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:self.evidence_failure=failure_details(error,'cleanup')
        connected=self.connected();ownership(deviceConnected=connected);require(connected,'cleanup-device-offline')
        absent=self.package_absent();ownership(packageAbsent=absent,transactionInstalled=self.installed)
        if absent:
            # 安装前失败时没有应用写入；不得伪造force-stop/uninstall证据。
            require(not self.installed,'installed-package-unexpectedly-absent')
            return {'confirmed':True,'appSelfCleanup':'not-started','deviceMutation':'none'}
        current=package_identity(observe('identity',lambda:self.hdc(['shell','bm','dump','-n',BUNDLE])),self.signing['certificateDER_SHA256'],self.version)
        require(self.installed,'install-ownership-unconfirmed')
        matched=self.installed_identity is not None and current==self.installed_identity;ownership(installationIdentityMatched=matched,lifecycleVerified=current['installationLifecycleVerified']);require(matched,'installed-lifecycle-changed')
        if self.recovering or self.process is None:require(current['installationLifecycleVerified'],'installation-lifecycle-unconfirmed')
        p=observe('prestop-pid',lambda:self.hdc(['shell','pidof',BUNDLE]))
        require(type(p.get('returncode')) is int and p['returncode'] in (0,1) and not p.get('timedOut') and p.get('stderr')=='' and isinstance(p.get('stdout'),str),'cleanup-prestop-pid-unknown')
        if p['stdout'].strip():require(self.process is not None and self.current_process()==self.process,'cleanup-pid-reused-or-unknown')
        else:require(p['stdout']=='','cleanup-prestop-pid-format')
        ownership(processMatched=True)
        records={}
        records['stop']=observe('stop',lambda:self.hdc(['shell','aa','force-stop',BUNDLE],15))
        deadline=time.monotonic()+5;deadline_code='cleanup-window-deadline'
        def bounded_query(name,command,global_command=False):
            remaining=deadline-time.monotonic();require(remaining>0,deadline_code)
            result=observe(name,lambda:self.call(command,remaining) if global_command else self.hdc(command,remaining))
            require(time.monotonic()<deadline,deadline_code)
            return result
        for attempt in range(3):
            # 每份窗口快照前独立确认连接、UDID、安装生命周期、PID和Ability；任何失败不重试掩盖。
            records['connection']=bounded_query('connection',[self.tools['hdc'],'list','targets','-v'],True)
            require(connected_output(records['connection'],self.serial),'cleanup-device-offline')
            device=bounded_query('device-id',['shell','bm','get','-u'])
            require(command_ok(device) and not device.get('stderr'),'device-id-query-failed')
            match=re.fullmatch(r'\s*udid of current device is[ \t]*:\s*([A-Za-z0-9_-]{8,256})\s*',device['stdout']);require(match is not None,'device-id-format')
            require(digest(match.group(1).encode())==self.approval['deviceIdSHA256'],'device-id-mismatch')
            identity=package_identity(bounded_query('identity',['shell','bm','dump','-n',BUNDLE]),self.signing['certificateDER_SHA256'],self.version)
            require(identity==self.installed_identity,'installed-lifecycle-changed')
            records['pid']=bounded_query('pid',['shell','pidof',BUNDLE])
            require(cleanup_proof({'pid':records['pid']},self.serial,self.process)['checks']['pid-absent'],'cleanup-pid-reused-or-unknown')
            records['ability']=bounded_query('ability',['shell','aa','dump','-a'])
            ability_checks=cleanup_proof({'ability':records['ability']},self.serial,self.process)['checks']
            require(ability_checks['ability-command-success'] and ability_checks['ability-absent'],'cleanup-ability-present-or-unknown')
            records['window']=bounded_query('window',['shell','hidumper','-s','WindowManagerService','-a','-a'])
            if attempt==2 or not window_resample_allowed(records['window'],self.process):break
            require('force stop process successfully' in records['stop'].get('stdout','') and command_ok(records['stop']) and not records['stop'].get('stderr'),'cleanup-stop-unconfirmed')
            time.sleep(min(0.1,max(0,deadline-time.monotonic())))
        pre_checks=cleanup_proof(records,self.serial,self.process)['checks']
        # 只有原有合法计数缺口允许后验；坏行、目标窗口或命令失败必须锁存失败。
        pre_window_valid=(pre_checks['window-command-success'] and pre_checks['window-absent']) or window_resample_allowed(records['window'],self.process)
        # 窗口查询后再核安装生命周期，防止卸载不属于本事务的新安装。
        current=package_identity(observe('identity',lambda:self.hdc(['shell','bm','dump','-n',BUNDLE])),self.signing['certificateDER_SHA256'],self.version)
        require(current==self.installed_identity,'installed-lifecycle-changed')
        records['uninstall']=observe('uninstall',lambda:self.hdc(['uninstall',BUNDLE],30))
        require(command_ok(records['uninstall']) and not records['uninstall'].get('stderr') and 'uninstall bundle successfully' in records['uninstall']['stdout'],'cleanup-uninstall-unconfirmed')
        # 卸载后仅一次新鲜完整快照。清理独立计时，不增加播放或窗口重采预算。
        phase='post-uninstall';deadline=time.monotonic()+5;deadline_code='cleanup-final-deadline'
        records['connection']=bounded_query('connection',[self.tools['hdc'],'list','targets','-v'],True)
        require(connected_output(records['connection'],self.serial),'cleanup-device-offline')
        device=bounded_query('device-id',['shell','bm','get','-u'])
        require(command_ok(device) and not device.get('stderr'),'device-id-query-failed')
        match=re.fullmatch(r'\s*udid of current device is[ \t]*:\s*([A-Za-z0-9_-]{8,256})\s*',device['stdout']);require(match is not None,'device-id-format')
        require(digest(match.group(1).encode())==self.approval['deviceIdSHA256'],'device-id-mismatch')
        records['packages']=bounded_query('packages',['shell','bm','dump','-a'])
        records['pid']=bounded_query('pid',['shell','pidof',BUNDLE])
        records['ability']=bounded_query('ability',['shell','aa','dump','-a'])
        records['window']=bounded_query('window',['shell','hidumper','-s','WindowManagerService','-a','-a'])
        result=cleanup_proof(records,self.serial,self.process)
        result['checks']['pre-uninstall-window-valid']=pre_window_valid
        if not pre_window_valid:result['failedChecks'].append('pre-uninstall-window-invalid')
        result['checks']['cleanup-evidence-retained']=not bool(getattr(self,'evidence_failure',None))
        if not result['checks']['cleanup-evidence-retained']:result['failedChecks'].append('cleanup-evidence-not-retained')
        result['confirmed']=all(result['checks'].values())
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
    parser=argparse.ArgumentParser(description='专用短测本地入口。默认只报告pending；--execute/--recover/--sign-verify-only须外部精确批准和专用材料。')
    for name in ['artifact','artifact-approval','execution-approval','signing-config','tools-lock','state-directory']:
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--execution-approval-sha256');modes=parser.add_mutually_exclusive_group();modes.add_argument('--execute',action='store_true');modes.add_argument('--recover',action='store_true');modes.add_argument('--sign-verify-only',action='store_true')
    args=parser.parse_args(argv)
    if not (args.execute or args.recover or args.sign_verify_only) or not all([args.artifact,args.artifact_approval,args.execution_approval,args.signing_config,args.tools_lock,args.state_directory,args.execution_approval_sha256]):
        print(json.dumps(local_readiness(args.execution_approval,args.signing_config,args.tools_lock)));return 2
    workspace=None
    try:
        require(os.uname().machine=='x86_64','imac-architecture-mismatch')
        actual={'controller':controller_identity(),'artifactApproval':digest(read_file(args.artifact_approval,262144)),'toolLock':digest(read_file(args.tools_lock,262144)),'signingConfig':digest(read_file(args.signing_config,262144))}
        approval=verify_execution_approval(args.execution_approval,args.execution_approval_sha256,actual,int(time.time()))
        require_action_scope('sign-verify-only' if args.sign_verify_only else 'recover' if args.recover else 'execute',approval)
        signing=signing_contract(read_json(read_file(args.signing_config,262144)),approval)
        lock=read_json(read_file(args.tools_lock,262144));tools=verify_device_tools(lock,signing)
        result=verify_artifact(args.artifact,args.artifact_approval,approval['artifactApprovalSHA256'])
        require(result['bundleName']==BUNDLE,'dedicated-bundle-required')
        archive=read_file(args.artifact);require(digest(archive)==result['zipSHA256'],'artifact-replaced')
        unsigned=read_zip_members(archive)['device-unsigned.hap'];members=read_zip_members(unsigned);metadata=read_json(members['module.json'])
        module=metadata['module'];require(not module.get('requestPermissions') and not module.get('extensionAbilities'),'device-package-network-or-backup')
        version=metadata['app']['versionCode'];require(type(version) is int and version>0,'package-version')
        if (args.execute or args.sign_verify_only) and (not sys.stdin.isatty() or not sys.stdout.isatty()):
            print(json.dumps({'status':'pending','pendingReason':'interactive-local-signing-required','deviceVerified':False,'formalArtifactAllowed':False}));return 2
        state=args.state_directory;require(state==STATE_DIRECTORY and not state.is_symlink(),'fixed-device-state-directory-required');state.mkdir(mode=0o700,exist_ok=True)
        # 可信控制器/工具校验在任何设备调用和私钥读取之前完成。
        def checked_command(command,timeout):
            require(controller_identity()==actual['controller'],'controller-changed')
            if args.sign_verify_only:require_sign_verify_command(command,tools)
            verify_invoked_tools(lock,signing,command)
            return run_command(command,timeout)
        requests={'nonce':approval['nonce'],'bundle':BUNDLE,'unsignedHapSHA256':result['unsignedHAP_SHA256']}
        # workspace仅本轮私有文件；recover使用新本地目录但不生成新的设备会话。
        import tempfile
        workspace=Path(tempfile.mkdtemp(prefix='session-'+approval['nonce']+'-',dir=state));os.chmod(workspace,0o700)
        unsigned_path=workspace/'device-unsigned.hap';unsigned_path.write_bytes(unsigned);os.chmod(unsigned_path,0o600)
        device=FixedDevice(tools,approval,signing,workspace/'private',unsigned_path,version,expected_unsigned_sha=result['unsignedHAP_SHA256'],command=checked_command)
        device.tool_guard=lambda:verify_device_tools(lock,signing)
        report=sign_verify_transaction(device,state,requests) if args.sign_verify_only else recover(device,state,requests) if args.recover else transaction(device,state,requests,execution_identity={'approvalSHA256':args.execution_approval_sha256,'controllerSHA256':actual['controller']})
        report['deviceVerified']=bool(args.execute and report.get('scenarioPassed'))
        report['controllerSHA256']=actual['controller'];report['approvalSHA256']=args.execution_approval_sha256
        if device.verification:report['signature']=device.verification
        print(json.dumps(report,ensure_ascii=False));return 0 if report.get('deviceVerified') or report.get('recovered') or (args.sign_verify_only and report.get('signatureVerified')) else 2 if report.get('status')=='pending' else 1
    except (ContractError,KeyError,TypeError,ValueError,OSError) as error:
        print(json.dumps({'status':'failed','failure':failure_details(error,'preflight'),'deviceVerified':False,'formalArtifactAllowed':False}));return 1
    finally:
        # 只删除本进程创建的临时目录；持久journal和用户签名材料始终保留。
        if workspace is not None:
            import shutil
            shutil.rmtree(workspace)

if __name__=='__main__':raise SystemExit(main())
