#!/usr/bin/env python3
"""手动云端准备与宿主只读收证；从不签名、安装、播放或生成执行批准。"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import io
import zipfile

HERE=Path(__file__).resolve().parent
CONTROLLER_SHA256='7d9a5cf0bcb22531f4435a5760f2df4d67d099aff60965ec80afd859c5f17363'
REPO='yaoshining/VidAll_Player'
WORKFLOW='.github/workflows/deveco26-pr82-gates.yml'
BUNDLE='com.yaoshining.vidalldeviceprobe'
STATE=Path.home()/'Library/Application Support/VidAllDeviceExecution/tv-192.168.3.85-5555'
RECEIPTS=Path.home()/'Library/Application Support/VidAllDeviceExecution/trusted/manual-workflow/receipts'
PREPARE_KEYS={'schemaVersion','mode','source','artifactId','zipSHA256','manifestSHA256','hapSHA256'}
COLLECT_KEYS={'schemaVersion','mode','nonce','preparedSHA256','journalSHA256','ledgerSHA256','smokeSHA256','executionApprovalSHA256','controllerSHA256'}
CLEANUP_CHECKS={'ability-absent','ability-command-success','cleanup-evidence-retained','device-connected','package-absent','pid-absent','pre-uninstall-window-valid','stop-command-success','stop-semantic-success','uninstall-command-success','uninstall-semantic-success','window-absent','window-command-success'}
POST=['connection','device-id','packages','pid','ability','window']

def require(condition,code):
    if not condition:raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n').encode()
def controller():
    path=HERE/'controller.py'
    require(not path.is_symlink() and sha(path.read_bytes())==CONTROLLER_SHA256,'trusted-controller-drift')
    spec=importlib.util.spec_from_file_location('manual_controller',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def request(data,expected,mode):
    c=controller();require(c.is_hash(expected) and isinstance(data,bytes) and 0<len(data)<=16384 and sha(data)==expected,'request-digest')
    r=c.read_json(data)
    require(mode in ('prepare','collect') and r.get('mode')==mode and type(r.get('schemaVersion')) is int and r['schemaVersion']==1,'request-mode')
    require(set(r)==(PREPARE_KEYS if mode=='prepare' else COLLECT_KEYS),'request-fields')
    if mode=='prepare':
        c.validate_source(r['source']);require(c.positive_integer(r['artifactId']),'artifact-id')
        require(r['source']['workflowPath']==WORKFLOW and r['source']['workflowSHA']==r['source']['eventMergeSHA'],'workflow-source')
        keys=['zipSHA256','manifestSHA256','hapSHA256']
    else:
        require(isinstance(r['nonce'],str) and re.fullmatch('[0-9a-f]{32}',r['nonce']),'request-nonce')
        keys=list(COLLECT_KEYS-{'schemaVersion','mode','nonce'})
    require(all(c.is_hash(r[k]) for k in keys),'request-hashes');return r

def prepare(r,get_json,download):
    """request摘要只绑定查询范围；不是用户授予签名/安装的执行批准。"""
    request(encoded(r),sha(encoded(r)),'prepare');c=controller();s=r['source']
    run=get_json(f"actions/runs/{s['runId']}/attempts/{s['runAttempt']}")
    require(run.get('id')==s['runId'] and run.get('run_attempt')==s['runAttempt'] and run.get('status')=='completed' and run.get('conclusion')=='success','attempt-not-success')
    require(run.get('repository',{}).get('id')==1307243374 and run['repository'].get('full_name')==REPO and run.get('head_repository',{}).get('id')==1307243374,'run-repository')
    require(run.get('head_sha')==s['headSHA'] and run.get('event')==s['event'] and run.get('path')==WORKFLOW,'run-source')
    commit=get_json('git/commits/'+s['eventMergeSHA'])
    require(commit.get('sha')==s['eventMergeSHA'] and commit.get('tree',{}).get('sha')==s['sourceTreeSHA'],'source-tree')
    if s['event']=='pull_request':
        prs=run.get('pull_requests',[]);require(len(prs)==1 and prs[0].get('head',{}).get('sha')==s['headSHA'],'run-pr')
        require([p.get('sha') for p in commit.get('parents',[])]==[prs[0].get('base',{}).get('sha'),s['headSHA']],'merge-parents')
    else:require(s['headSHA']==s['eventMergeSHA'],'non-pr-source')
    a=get_json('actions/artifacts/'+str(r['artifactId']));w=a.get('workflow_run',{})
    require(a.get('id')==r['artifactId'] and a.get('expired') is False and a.get('digest')=='sha256:'+r['zipSHA256'],'artifact-metadata')
    require(a.get('name')==f"device-unsigned-{s['eventMergeSHA']}-{s['runAttempt']}" and w.get('id')==s['runId'] and w.get('head_sha')==s['headSHA'] and w.get('repository_id')==w.get('head_repository_id')==1307243374,'artifact-run')
    b=download(r['artifactId']);require(len(b)==a.get('size_in_bytes') and sha(b)==r['zipSHA256'],'zip-digest')
    members=c.read_zip_members(b);require(set(members)=={'manifest.json','device-unsigned.hap'},'artifact-members')
    mb=members['manifest.json'];require(sha(mb)==r['manifestSHA256'],'manifest-digest');m=c.read_json(mb)
    require(set(m)==c.MANIFEST_KEYS and type(m['schemaVersion']) is int and m['schemaVersion']==1 and m['source']==s and m['bundleName']==BUNDLE,'manifest-source')
    hap=members['device-unsigned.hap'];require(m['hap']=={'path':'device-unsigned.hap','bytes':len(hap),'sha256':r['hapSHA256']} and sha(hap)==r['hapSHA256'],'hap-digest')
    c.verify_hap(hap,m)
    with zipfile.ZipFile(io.BytesIO(hap)) as z:
        names=z.namelist();require(not any(n.lower().endswith(('.p12','.p7b','.cer','.pem')) or n.startswith('META-INF/') or n=='.pages.info' for n in names),'unsigned-only')
        last=max(i.header_offset+30+len(i.filename.encode())+len(i.extra)+i.compress_size+(16 if i.flag_bits&8 else 0) for i in z.infolist())
        require(last==z.start_dir,'unsigned-signing-block')
    # 只生成准备记录，绝不构造controller的执行approval或可用nonce。
    return {'schemaVersion':1,'status':'waiting-local-execution','artifactVerified':True,'executionAuthorized':False,'deviceVerified':False,'formalArtifactAllowed':False,'requestSHA256':sha(encoded(r)),'source':s,'artifactId':r['artifactId'],'zipSHA256':r['zipSHA256'],'manifestSHA256':r['manifestSHA256'],'unsignedHAP_SHA256':r['hapSHA256'],'bundleName':BUNDLE}

def private_directory(path):
    for item in [path,*path.parents]:
        require(not item.is_symlink(),'private-directory-symlink')
    st=path.stat();require(stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and not st.st_mode&0o077,'private-directory-permissions')

def local_record(path,expected):
    c=controller();require(c.is_hash(expected),'record-hash')
    try:st=path.lstat()
    except OSError as error:raise ValueError('record-unavailable') from error
    require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.geteuid() and not st.st_mode&0o077,'record-permissions')
    b=c.read_file(path,2*1024*1024);require(sha(b)==expected,'record-drift');return c.read_json(b)

def host_idle(text):
    require(isinstance(text,str) and 0<len(text)<=2*1024*1024,'host-query-invalid')
    for line in text.splitlines():
        row=re.fullmatch(r'\s*([1-9][0-9]*)\s+(.+)',line);require(row is not None,'host-query-format')
        command=row[2]
        require(not re.search(r'(?:^|/)(?:imac|reconciliation)\.py(?:\s|$)',command) and not re.search(r'(?:^|/)vidall-deviceprobe-[A-Za-z0-9_-]+\.command(?:\s|$)',command) and 'hap-sign-tool.jar sign-app' not in command,'host-execution-active')

def validate_collected(r,prepared,journal,ledger,smoke):
    c=controller();s=prepared.get('source');c.validate_source(s)
    require(prepared.get('status')=='waiting-local-execution' and prepared.get('artifactVerified') is True and prepared.get('executionAuthorized') is False and prepared.get('deviceVerified') is False and prepared.get('formalArtifactAllowed') is False,'prepared-not-ready')
    require(journal.get('status')=='complete' and smoke.get('status')=='passed','transaction-not-complete')
    binding=journal.get('binding',{});require(binding==smoke.get('binding') and binding.get('nonce')==r['nonce'] and binding.get('bundle')==prepared.get('bundleName')==BUNDLE and binding.get('unsignedHapSHA256')==prepared.get('unsignedHAP_SHA256'),'transaction-binding')
    require(all(type(binding.get(k)) is int and binding[k]>0 for k in ['pid','startedAtMs','processStartTicks']),'recorded-process-missing')
    nonces=ledger.get('nonces');require(isinstance(nonces,list) and len(nonces)==len(set(nonces)) and all(isinstance(n,str) and re.fullmatch('[0-9a-f]{32}',n) for n in nonces) and r['nonce'] in nonces,'ledger-nonce')
    require(smoke.get('approvalSHA256')==r['executionApprovalSHA256'] and smoke.get('controllerSHA256')==r['controllerSHA256'],'execution-identity')
    require(not any(k in item for item in [journal,smoke] for k in ['failure','cleanupFailure','evidenceFailure']),'recorded-failure')
    require(smoke.get('scenarioPassed') is True and smoke.get('deviceVerified') is True and smoke.get('formalArtifactAllowed') is False and smoke.get('installedPayloadVerified') is True and journal.get('installed',{}).get('installedPayloadVerified') is True,'recorded-result')
    sig=smoke.get('signature',{});require(smoke.get('signatureVerified') is True and smoke.get('signatureStatus')=='verified' and all(sig.get(k) is True for k in ['signatureVerified','payloadEqual','derivedPagesVerified']) and sig.get('unsignedHAP_SHA256')==binding['unsignedHapSHA256'] and c.is_hash(sig.get('signedHAP_SHA256')) and type(sig.get('membersCompared')) is int and sig['membersCompared']>0,'recorded-signature')
    cleanup=smoke.get('cleanup',{});require(cleanup==journal.get('cleanup') and cleanup.get('confirmed') is True and cleanup.get('appSelfCleanup')=='confirmed' and cleanup.get('failedChecks')==[] and set(cleanup.get('checks',{}))==CLEANUP_CHECKS and all(v is True for v in cleanup['checks'].values()),'recorded-cleanup')
    history=smoke.get('cleanupCommandHistory');require(isinstance(history,list) and 6<=len(history)<=32 and [x.get('name') for x in history[-6:]]==POST,'post-query-history')
    for x in history[-6:]:
        require(x.get('phase')=='post-uninstall' and type(x.get('exitCode')) is int and x['exitCode'] in ((0,1) if x['name']=='pid' else (0,)) and x.get('timedOut') is False and x.get('interrupted') is False and x.get('stderrEmpty') is True,'post-query-failed')
    w=history[-1].get('windowEvidence',{});require(w.get('code')=='ok' and all(w.get(k) is True for k in ['parsePassed','commandPassed','absenceConfirmed']) and type(w.get('reportedTotal')) is int and w['reportedTotal']>=0 and w.get('observedRows')==w['reportedTotal'],'post-window-incomplete')
    events=smoke.get('events',{});rows=events.get('rows',[]);require(isinstance(rows,list) and events.get('count')==len(rows) and 1<=len(rows)<=2048 and events.get('truncated',False) is False,'recorded-events')
    require(all(x.get('seq')==i and x.get('bindingMismatch') is False and type(x.get('elapsedMs')) is int and 0<=x['elapsedMs']<=120000 for i,x in enumerate(rows,1)),'event-binding')
    require([x['elapsedMs'] for x in rows]==sorted(x['elapsedMs'] for x in rows),'event-time-order')
    require(rows[-1].get('event')=='session-end' and rows[-1].get('value')=='passed' and any(x.get('event')=='keep-screen' and x.get('value')=='false' for x in rows),'recorded-session-end')
    # 固定输出白名单：不复制nonce、设备标识、证书/Profile、原命令或事件全文。
    return {'schemaVersion':1,'status':'local-execution-evidence-verified','recordedDeviceVerified':True,'deviceCheckedNow':False,'executionAuthorized':False,'formalArtifactAllowed':False,'source':s,'artifactId':prepared['artifactId'],'unsignedHAP_SHA256':binding['unsignedHapSHA256'],'preparedSHA256':r['preparedSHA256'],'executionApprovalSHA256':r['executionApprovalSHA256'],'controllerSHA256':r['controllerSHA256'],'journalSHA256':r['journalSHA256'],'ledgerSHA256':r['ledgerSHA256'],'smokeSHA256':r['smokeSHA256'],'sessionIdentitySHA256':sha(r['nonce'].encode()),'events':len(rows),'durationMs':rows[-1]['elapsedMs'],'cleanupHistoryCount':len(history),'finalWindowRows':w['observedRows'],'applicationKeepScreenReleased':True,'scope':'既有本地手动执行记录；不是本轮重新访问设备'}

def collect(r,state=STATE,receipts=RECEIPTS,ps=None):
    request(encoded(r),sha(encoded(r)),'collect');c=controller();private_directory(state);private_directory(receipts)
    require((state/'device.lock').is_file() and not (state/'device.lock').is_symlink(),'existing-lease-required')
    if ps is None:
        def ps():
            p=subprocess.run(['/bin/ps','-axo','pid=,command='],capture_output=True,text=True,timeout=10)
            require(p.returncode==0 and not p.stderr,'host-query-failed');return p.stdout
    with c.DeviceLease(state/'device.lock'):
        require(not any(state.glob('session-*')),'active-session');host_idle(ps())
        prepared=local_record(receipts/(r['preparedSHA256']+'.json'),r['preparedSHA256'])
        files=[('journal.json',r['journalSHA256']),('used-nonces.json',r['ledgerSHA256']),('smoke-'+r['nonce']+'.json',r['smokeSHA256'])]
        j,l,s=[local_record(state/name,digest) for name,digest in files]
        out=validate_collected(r,prepared,j,l,s)
        # 即使存在不遵守lease的外部修改，收尾CAS仍拒绝。
        for name,digest in files:local_record(state/name,digest)
        require(not any(state.glob('session-*')),'active-session');host_idle(ps());return out

class GitHub:
    def get(self,path):
        require(re.fullmatch(r'(?:actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*|actions/artifacts/[1-9][0-9]*|git/commits/[0-9a-f]{40})',path),'api-path')
        return controller().read_json(self.call(path,2*1024*1024))
    def call(self,path,limit):
        p=subprocess.run(['gh','api','repos/'+REPO+'/'+path],capture_output=True,timeout=90)
        require(p.returncode==0 and 0<len(p.stdout)<=limit,'github-read-failed');return p.stdout
    def download(self,aid):return self.call('actions/artifacts/'+str(aid)+'/zip',128*1024*1024)

def main():
    parser=argparse.ArgumentParser(description='手动prepare/collect；不执行设备操作')
    parser.add_argument('mode',choices=['prepare','collect']);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    require(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and os.environ.get('GITHUB_REF')=='refs/heads/main','workflow-context')
    raw=os.environ.get('MANUAL_REQUEST','').encode();r=request(raw,os.environ.get('MANUAL_REQUEST_SHA256',''),args.mode)
    if args.mode=='prepare':api=GitHub();result=prepare(r,api.get,api.download)
    else:require(sys.platform=='darwin','collect-host');result=collect(r)
    # 输出目录由固定workflow runner.temp决定；不接受request中的路径。
    require(not args.out.exists() and not args.out.is_symlink(),'output-exists');args.out.mkdir(mode=0o700)
    result['dispatchRequestSHA256']=sha(raw);(args.out/'result.json').write_bytes(encoded(result));print(json.dumps({'status':result['status'],'formalArtifactAllowed':False}))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired):
        print('手动证据门禁失败；未执行签名或设备命令。',file=sys.stderr);raise SystemExit(1)
