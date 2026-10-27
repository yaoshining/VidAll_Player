#!/usr/bin/env python3
"""仅清理现状对账：固定只读命令；不改变原短测失败、nonce或设备状态。"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from controller import ContractError, DeviceLease, digest, is_hash, read_file, read_json, require
from executor import BUNDLE, safe_command_result
import imac as M

HERE=Path(__file__).resolve().parent
CHECKS=['deviceIdentity','packageAbsent','processAbsent','abilityAbsent','windowAbsent','hostInactive','noSessions']
COMMANDS=['cli','connection','identity','packages','pid','ability','window','host','connectionFinal','identityFinal']
CODE_FILES=['reconciliation.py','controller.py','executor.py','imac.py']

def encoded(value):return (json.dumps(value,sort_keys=True)+'\n').encode()

def code_identity():
    return digest(b''.join(name.encode()+b'\0'+read_file(HERE/name) for name in CODE_FILES))

def validate_approval(data,expected,tools_data,now):
    require(is_hash(expected) and digest(data)==expected,'reconciliation-approval-digest')
    a=read_json(data)
    fields={'schemaVersion','purpose','nonce','oldNonce','oldJournalSHA256','oldLedgerSHA256','codeSHA256','toolsLockSHA256','stateDirectory','deviceSerial','deviceIdSHA256','bundleName','issuedAt','expiresAt','allowDeviceMutation','allowHeadAdvance','python','ps','nextExecutionApprovalSHA256'}
    require(set(a)==fields and type(a['schemaVersion']) is int and a['schemaVersion']==1,'reconciliation-approval-schema')
    require(a['purpose']=='cleanup-only-reconciliation' and a['allowDeviceMutation'] is False and a['allowHeadAdvance'] is True,'reconciliation-scope')
    require(a['stateDirectory']==str(M.STATE_DIRECTORY) and a['deviceSerial']=='192.168.3.85:5555' and a['bundleName']==BUNDLE,'reconciliation-target')
    require(all(isinstance(a[k],str) and re.fullmatch('[0-9a-f]{32}',a[k]) for k in ['nonce','oldNonce']) and a['nonce']!=a['oldNonce'],'reconciliation-nonce')
    require(all(is_hash(a[k]) for k in ['oldJournalSHA256','oldLedgerSHA256','codeSHA256','toolsLockSHA256','deviceIdSHA256','nextExecutionApprovalSHA256']),'reconciliation-hash')
    require(type(a['issuedAt']) is int and type(a['expiresAt']) is int and a['issuedAt']<=now<a['expiresAt']<=a['issuedAt']+86400,'reconciliation-expired')
    require(a['codeSHA256']==code_identity() and a['toolsLockSHA256']==digest(tools_data),'reconciliation-input-drift')
    for key,path in [('python','/Library/Developer/CommandLineTools/usr/bin/python3'),('ps','/bin/ps')]:
        require(set(a[key])==({'path','resolvedPath','sha256'} if key=='python' else {'path','sha256'}) and a[key]['path']==path and is_hash(a[key]['sha256']),'reconciliation-host-tool')
        target=Path(path).resolve() if key=='python' else Path(path)
        if key=='python':require(str(target)==a[key]['resolvedPath'],'reconciliation-interpreter-target-drift')
        require(digest(read_file(target))==a[key]['sha256'],'reconciliation-host-tool-drift')
    return a

def exclusive_write(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())

def sync_directory(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def unchanged(state,a):
    require(digest(read_file(state/'journal.json',262144))==a['oldJournalSHA256'],'reconciliation-journal-drift')
    require(digest(read_file(state/'used-nonces.json',262144))==a['oldLedgerSHA256'],'reconciliation-ledger-drift')

def commit_head(state,a,data):
    """持锁的最后一步；先持久化全部准备数据，CAS 后没有其他可失败写入。"""
    temp=state/('reconciliation-'+a['nonce']+'.head.tmp')
    exclusive_write(temp,data);sync_directory(state)
    unchanged(state,a)
    # rename 是提交点。崩溃后用可变头引用及准备证据判定，不自动重复运行。
    os.replace(temp,state/'journal.json')

def safe_proof(proof,started,now):
    require(isinstance(proof,dict) and set(proof)=={'checks','commands','observedAt'},'reconciliation-proof-schema')
    require(set(proof['checks'])==set(CHECKS) and all(type(v) is bool for v in proof['checks'].values()),'reconciliation-check-schema')
    require(type(proof['observedAt']) is int and started<=proof['observedAt']<=now and now-started<=180,'reconciliation-stale-proof')
    require(isinstance(proof['commands'],dict) and set(proof['commands'])==set(COMMANDS),'reconciliation-command-schema')
    for item in proof['commands'].values():
        require(isinstance(item,dict) and set(item)=={'exitCode','timedOut','interrupted','stdoutBytes','stdoutSHA256','stdoutEmpty','stderrBytes','stderrSHA256','stderrEmpty'},'reconciliation-command-fields')
        for k,v in item.items():
            if k.endswith('SHA256'):require(is_hash(v),'reconciliation-command-hash')
            elif k.endswith('Bytes'):require(type(v) is int and 0<=v<=2*1024*1024,'reconciliation-command-size')
            elif k=='exitCode':require(type(v) is int and -255<=v<=255,'reconciliation-command-exit')
            else:require(type(v) is bool,'reconciliation-command-boolean')
    require(all(proof['checks'].values()),'reconciliation-presence-or-unknown')
    return proof

def reconcile(state,a,approval_sha,device,clock=time.time):
    state=Path(state);require(state.is_dir() and not state.is_symlink(),'reconciliation-state')
    require(is_hash(approval_sha),'reconciliation-approval-required')
    with DeviceLease(state/'device.lock'):
        started=int(clock());require(a['issuedAt']<=started<a['expiresAt'],'reconciliation-expired')
        unchanged(state,a);raw=read_file(state/'journal.json',262144);old=read_json(raw);ledger=read_json(read_file(state/'used-nonces.json',262144))
        require(old.get('status')=='cleanup-unknown' and old.get('binding',{}).get('nonce')==a['oldNonce'] and old['binding'].get('bundle')==BUNDLE,'reconciliation-old-session')
        nonces=ledger.get('nonces');require(set(ledger)=={'nonces'} and isinstance(nonces,list) and all(isinstance(n,str) and re.fullmatch('[0-9a-f]{32}',n) for n in nonces) and len(nonces)==len(set(nonces)) and a['oldNonce'] in nonces and a['nonce'] not in nonces,'reconciliation-ledger')
        stem='reconciliation-'+a['nonce'];archive=state/(stem+'.original.json');record=state/(stem+'.evidence.json');temp=state/(stem+'.head.tmp')
        require(not any(p.exists() or p.is_symlink() for p in [archive,record,temp]),'reconciliation-already-prepared')
        proof=safe_proof(device.snapshot(old),started,int(clock()));require(int(clock())<a['expiresAt'],'reconciliation-expired')
        unchanged(state,a)
        exclusive_write(archive,raw)
        evidence={'schemaVersion':1,'purpose':'cleanup-only-reconciliation','nonce':a['nonce'],'oldNonce':a['oldNonce'],'approvalSHA256':approval_sha,'oldJournalSHA256':a['oldJournalSHA256'],'oldLedgerSHA256':a['oldLedgerSHA256'],'archive':archive.name,'proof':proof,'decision':'cleanup-only-verified','headCommit':'requires-journal-reference','scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False}
        record_bytes=encoded(evidence);exclusive_write(record,record_bytes);sync_directory(state)
        head={**old,'status':'complete','reconciliation':{'record':record.name,'recordSHA256':digest(record_bytes),'approvalSHA256':approval_sha,'oldJournalSHA256':a['oldJournalSHA256'],'cleanupOnly':True,'scenarioPassed':False}}
        commit_head(state,a,encoded(head))
        return {'reconciled':True,'scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False,'recordSHA256':digest(record_bytes),'journalSHA256':digest(encoded(head))}

class ReadOnlyDevice:
    def __init__(self,a,lock,command=M.run_command,clock=time.time):self.a=a;self.lock=lock;self.command=command;self.clock=clock;self.records={}
    def guard(self,command):
        require(code_identity()==self.a['codeSHA256'],'reconciliation-input-drift')
        tools=self.lock['tools'];h=tools['hdc']['path'];n=tools['node']['path'];c=tools['cli']['path'];s=self.a['deviceSerial']
        allowed=[[n,c,'device','list'],[h,'list','targets','-v'],[h,'-t',s,'shell','bm','get','-u'],[h,'-t',s,'shell','bm','dump','-a'],[h,'-t',s,'shell','pidof',BUNDLE],[h,'-t',s,'shell','aa','dump','-a'],[h,'-t',s,'shell','hidumper','-s','WindowManagerService','-a','-a'],[self.a['ps']['path'],'-axo','pid=,command=']]
        require(command in allowed,'reconciliation-command-denied')
        names=['node','cli'] if command[0]==n else ['hdc'] if command[0]==h else []
        for name in names:require(digest(read_file(tools[name]['path']))==tools[name]['sha256'],'reconciliation-tool-drift')
        if command[0]==n:
            closure=self.lock['cliClosure'];actual=M.runtime_tree(closure['packageRoot']);require(actual['files']==closure['files'] and actual['treeSHA256']==closure['treeSHA256'],'reconciliation-cli-drift')
        if command[0]==self.a['ps']['path']:require(digest(read_file(command[0]))==self.a['ps']['sha256'],'reconciliation-tool-drift')
    def call(self,name,args):
        self.guard(args)
        try:r=self.command(args,15)
        except (ContractError,TimeoutError,OSError) as error:
            self.records[name]=safe_command_result(error=error);raise
        self.records[name]=safe_command_result(r);return r
    def snapshot(self,old):
        a=self.a;s=a['deviceSerial'];t=self.lock['tools'];h=t['hdc']['path'];prefix=[h,'-t',s,'shell'];checks={k:False for k in CHECKS}
        cli=self.call('cli',[t['node']['path'],t['cli']['path'],'device','list'])
        require(M.command_ok(cli) and cli.get('stderr','') in ('','- Querying connected devices…\n') and s in cli['stdout'],'reconciliation-cli-offline')
        def identity(suffix):
            con=self.call('connection'+suffix,[h,'list','targets','-v']);require(M.connected_output(con,s),'reconciliation-device-offline')
            r=self.call('identity'+suffix,prefix+['bm','get','-u']);require(M.command_ok(r) and not r.get('stderr'),'reconciliation-device-query')
            match=re.fullmatch(r'\s*udid of current device is[ \t]*:\s*([A-Za-z0-9_-]{8,256})\s*',r['stdout'])
            require(match is not None and digest(match.group(1).encode())==a['deviceIdSHA256'],'reconciliation-device-identity')
        identity('')
        checks['packageAbsent']=BUNDLE not in M.package_list(self.call('packages',prefix+['bm','dump','-a']))
        pid=self.call('pid',prefix+['pidof',BUNDLE]);checks['processAbsent']=type(pid.get('returncode')) is int and pid['returncode'] in (0,1) and not pid.get('timedOut') and pid.get('stdout')=='' and not pid.get('stderr')
        old_pid=old['binding'].get('pid');require(type(old_pid) is int and old_pid>0,'reconciliation-old-process')
        ability=self.call('ability',prefix+['aa','dump','-a']);text=ability.get('stdout','')
        checks['abilityAbsent']=M.command_ok(ability) and not ability.get('stderr') and any(v in text for v in ['AbilityManagerService','current mission lists','AbilityRecord']) and BUNDLE not in text and not re.search(r'(?<!\d)'+str(old_pid)+r'(?!\d)',text)
        window=self.call('window',prefix+['hidumper','-s','WindowManagerService','-a','-a']);text=window.get('stdout','')
        checks['windowAbsent']=M.command_ok(window) and not window.get('stderr') and BUNDLE not in text and old_pid not in M.window_pids(text)
        host=self.call('host',[a['ps']['path'],'-axo','pid=,command=']);require(M.command_ok(host) and not host.get('stderr'),'reconciliation-host-query')
        active=False
        for line in host['stdout'].splitlines():
            row=re.fullmatch(r'\s*([1-9][0-9]*)\s+(.+)',line);require(row is not None,'reconciliation-host-format')
            if int(row[1])!=os.getpid() and (re.search(r'(?:^|/)(?:imac|reconciliation)\.py(?:\s|$)',row[2]) or re.search(r'(?:^|/)vidall-deviceprobe-[A-Za-z0-9_-]+\.command(?:\s|$)',row[2]) or 'hap-sign-tool.jar sign-app' in row[2]):active=True
        checks['hostInactive']=not active
        checks['noSessions']=not any(Path(a['stateDirectory']).glob('session-*'))
        identity('Final');checks['deviceIdentity']=True
        return {'checks':checks,'commands':self.records,'observedAt':int(self.clock())}

def main(argv=None):
    p=argparse.ArgumentParser(description='独立仅清理对账；必须精确批准，禁止任何设备写命令。')
    p.add_argument('--approval',type=Path,required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--tools-lock',type=Path,required=True);p.add_argument('--execute-reconciliation',action='store_true');args=p.parse_args(argv)
    try:
        data=read_file(args.tools_lock,262144);a=validate_approval(read_file(args.approval,262144),args.approval_sha256,data,int(time.time()))
        require(os.uname().machine=='x86_64' and Path(sys.executable).resolve()==Path(a['python']['path']).resolve(),'reconciliation-interpreter')
        lock=read_json(data);require(lock.get('architecture')=='x86_64' and lock.get('deviceSerial')==a['deviceSerial'],'reconciliation-tools-scope')
        require(set(lock['tools'])=={'java','signTool','hdc','node','cli'},'reconciliation-tools-fields')
        for tool in lock['tools'].values():require(set(tool)=={'path','sha256'} and is_hash(tool['sha256']) and digest(read_file(tool['path']))==tool['sha256'],'reconciliation-tool-drift')
        if not args.execute_reconciliation:print(json.dumps({'status':'pending','reason':'explicit-reconciliation-execution-required'}));return 2
        print(json.dumps(reconcile(Path(a['stateDirectory']),a,args.approval_sha256,ReadOnlyDevice(a,lock))));return 0
    except (ContractError,OSError,ValueError,KeyError,TypeError,KeyboardInterrupt,SystemExit) as error:
        code=str(error) if isinstance(error,ContractError) and re.fullmatch('reconciliation-[a-z-]+',str(error)) else 'reconciliation-interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'reconciliation-operation-failed'
        print(json.dumps({'status':'failed','code':code,'reconciled':False,'scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False}));return 1

if __name__=='__main__':raise SystemExit(main())
