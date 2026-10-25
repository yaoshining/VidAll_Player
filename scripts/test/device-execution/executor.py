#!/usr/bin/env python3
"""固定验签、短测事件与持久事务门禁；宿主替身不产生真机通过。"""
import base64
import json
import os
from pathlib import Path
import re
from controller import ContractError, DeviceLease, compare_signed_payload, digest, read_file, read_json, require

BUNDLE = 'com.yaoshining.vidalldeviceprobe'

def certificate_ders(data):
    """官方输出顺序没有叶子保证；解析全部PEM后按批准DER唯一匹配。"""
    blocks=re.findall(rb'-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\s]+?)\s*-----END CERTIFICATE-----',data)
    require(bool(blocks),'certificate-pem-missing')
    try: return [base64.b64decode(re.sub(rb'\s',b'',b),validate=True) for b in blocks]
    except ValueError as error: raise ContractError('certificate-format') from error

def official_ok(run,args,timeout=30):
    try: result=run([str(x) for x in args],timeout)
    except TimeoutError as error: raise ContractError('official-tool-timeout') from error
    require(isinstance(result,dict) and type(result.get('returncode')) is int and result['returncode']==0,'official-tool-failed')
    return result

def verify_signed(unsigned,signed,config,tools,work,run,now,device_id):
    """全新私有输出；官方verify-app→verify-profile→批准身份→全payload。"""
    work=Path(work);require(not work.exists() and not work.is_symlink(),'verification-output-reused');work.mkdir(mode=0o700)
    before=digest(read_file(signed));unsigned_sha=digest(read_file(unsigned))
    cert=work/'cert-chain.pem';profile=work/'profile.p7b';result=work/'profile-result.json'
    official_ok(run,[tools['java'],'-jar',tools['signTool'],'verify-app','-inFile',signed,'-outCertChain',cert,'-outProfile',profile])
    certs=[digest(d) for d in certificate_ders(read_file(cert,1024*1024))];cert_sha=config['certificateDER_SHA256']
    require(certs.count(cert_sha)==1,'signed-certificate-mismatch')
    require(digest(read_file(profile,1024*1024))==config['profileSHA256'],'signed-profile-mismatch')
    official_ok(run,[tools['java'],'-jar',tools['signTool'],'verify-profile','-inFile',profile,'-outFile',result])
    verified=read_json(read_file(result,1024*1024))
    require(verified.get('verifiedPassed') is True and isinstance(verified.get('content'),dict),'profile-verification-failed')
    content=verified['content'];validity=content.get('validity',{});bundle=content.get('bundle-info',{});debug=content.get('debug-info',{})
    require(content.get('type')=='debug' and bundle.get('bundle-name')==config['bundleName']==BUNDLE,'profile-bundle-or-type')
    require(type(validity.get('not-before')) is int and type(validity.get('not-after')) is int and validity['not-before']<=now<validity['not-after'],'profile-validity')
    development=bundle.get('development-certificate');require(isinstance(development,str),'profile-certificate-missing')
    require([digest(d) for d in certificate_ders(development.encode())]==[cert_sha],'profile-certificate-mismatch')
    require(debug.get('device-id-type')=='udid' and isinstance(debug.get('device-ids'),list) and device_id in debug['device-ids'],'profile-device-denied')
    require(digest(device_id.encode())==config['deviceIdSHA256'],'approved-device-mismatch')
    # 普通verify-app的证书Store并不保证首项或任意成员就是CMS signer。
    signer_result=official_ok(run,[tools['java'],'-cp',tools['signerHelperClassPath']+os.pathsep+str(tools['signTool']),'ActualSigner',signed,before,cert_sha])
    signer=read_json(signer_result['stdout'].encode())
    require(signer.get('schemaVersion')==1 and signer.get('verified') is True and type(signer.get('signerCount')) is int and signer['signerCount']==1 and signer.get('signedHAP_SHA256')==before and signer.get('actualSignerDER_SHA256')==cert_sha,'actual-signer-mismatch')
    comparison=compare_signed_payload(unsigned,signed)
    require(digest(read_file(signed))==before and digest(read_file(unsigned))==unsigned_sha,'package-changed-during-verification')
    return {**comparison,'signatureVerified':True,'signedHAP_SHA256':before,'unsignedHAP_SHA256':unsigned_sha,'certificateDER_SHA256':cert_sha,'profileSHA256':config['profileSHA256'],'deviceVerified':False}

def numeric(value): return type(value) in (int,float) and abs(value)<10**15

def validate_events(events,binding):
    require(isinstance(events,list) and 1<=len(events)<=2048,'events-missing-or-excessive')
    require(binding.get('bundle')==BUNDLE and re.fullmatch('[0-9a-f]{32}',binding.get('nonce','')) and type(binding.get('pid')) is int and binding['pid']>0,'session-binding')
    elapsed=-1
    for seq,row in enumerate(events,1):
        require(isinstance(row,dict) and row.get('schemaVersion')==1 and row.get('seq')==seq,'event-order')
        require(all(row.get(key)==binding.get(key) for key in ['nonce','bundle','pid','startedAtMs','unsignedHapSHA256']),'event-session-mismatch')
        require(type(row.get('elapsedMs')) is int and elapsed<=row['elapsedMs']<=120000,'event-time');elapsed=row['elapsedMs']
        require(row.get('event') not in ('session-failed','release-failed','keep-screen-failed','terminal','player-error'),'session-failed')
    def one(event,cycle=None):
        found=[(i,r) for i,r in enumerate(events) if r.get('event')==event and (cycle is None or r.get('cycle')==cycle)]
        require(len(found)==1,'event-missing-or-repeated:'+event);return found[0]
    def payload(row):
        require(isinstance(row.get('value'),str),'event-value');return read_json(row['value'].encode())
    ordered=[('session-start',None),('runtime-ready',None),('frame',1),('progress',1),('paused',None),('resumed',None),('seek-request',None),('seek-complete',None),('closed',None),('frame',2),('reopened',None),('progress',2),('eof',None),('release-complete',None),('session-end',None)]
    order=[one(e,c)[0] for e,c in ordered];require(order==sorted(order) and len(set(order))==len(order),'scenario-order')
    require(events[0]['event']=='session-start' and events[-1]['event']=='session-end' and events[-1]['value']=='passed','session-completion')
    require(one('runtime-ready')[1]['value']=='ready','runtime-not-ready')
    for event,cycle in [('progress',1),('resumed',1),('progress',2)]:
        d=payload(one(event,cycle)[1]);require(all(numeric(d.get(k)) for k in ['beforeMs','afterMs','intervalMs']) and d['intervalMs']>=500 and d['afterMs']-d['beforeMs']>=500,'progress-not-observed')
    paused=payload(one('paused')[1]);require(paused.get('paused') is True and all(numeric(paused.get(k)) for k in ['beforeMs','afterMs','intervalMs']) and paused['intervalMs']>=1000 and abs(paused['afterMs']-paused['beforeMs'])<=180,'pause-not-stable')
    requested=payload(one('seek-request')[1]);sought=payload(one('seek-complete')[1])
    require(requested.get('targetMs')==sought.get('targetMs')==10000 and numeric(sought.get('reachedMs')) and numeric(sought.get('afterMs')) and abs(sought['reachedMs']-10000)<=1000 and sought['afterMs']-sought['reachedMs']>=500,'seek-not-observed')
    frames=[payload(one('frame',i)[1]) for i in [1,2]]
    require(all(type(d.get('count')) is int and d['count']>0 and d.get('evidence')=='public-firstFrame-render-event' for d in frames) and frames[1]['count']>frames[0]['count'],'render-not-observed')
    eof=payload(one('eof')[1]);require(eof.get('completed') is True and numeric(eof.get('positionMs')) and eof['positionMs']>=28000 and numeric(eof.get('durationMs')) and abs(eof['durationMs']-30000)<=100,'eof-not-observed')
    screen=[r for r in events if r.get('event')=='keep-screen'];require(len(screen)==2 and [r['value'] for r in screen]==['true','false'] and events.index(screen[-1])>one('release-complete')[0],'keep-screen-not-released')
    require(one('closed')[1]['value']=='released' and one('release-complete')[1]['value']=='released' and one('reopened')[1]['value']=='new-first-frame','lifecycle-not-confirmed')
    return {'passed':True,'elapsedMs':elapsed,'appSelfCleanup':'confirmed','scope':'short-local-smoke','runtimeMappedLibraryHashVerified':False}

def save_state(path,data):
    """安装前先落盘；原子替换/fsync保留宿主中断后的阻塞记录。"""
    temp=path.with_suffix('.tmp');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as stream: stream.write(json.dumps(data,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path);directory=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if temp.exists():temp.unlink()

def transaction(platform,state_dir,binding):
    require(set(binding)=={'nonce','bundle','unsignedHapSHA256'},'caller-cannot-declare-process-identity')
    state=Path(state_dir);require(not state.is_symlink(),'state-symlink');state.mkdir(mode=0o700,parents=False,exist_ok=True)
    journal=state/'journal.json';used=state/'used-nonces.json'
    result={'status':'pending','scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False,'runtimeMappedLibraryHashVerified':False}
    with DeviceLease(state/'device.lock'):
        previous=read_json(read_file(journal)) if journal.exists() else {};require(previous.get('status') not in ('active','cleanup-unknown'),'pending-cleanup-journal')
        nonces=read_json(read_file(used)).get('nonces',[]) if used.exists() else [];require(binding['nonce'] not in nonces,'consumed-session-nonce')
        if not platform.connected():return {**result,'pendingReason':'device-offline'}
        if not platform.package_absent():return {**result,'pendingReason':'existing-package-not-owned'}
        save_state(used,{'nonces':[*nonces,binding['nonce']]});save_state(journal,{'status':'active','binding':binding})
        function_passed=False;cleanup={'confirmed':False,'appSelfCleanup':'unconfirmed'}
        try:
            installed=platform.install();require(installed.get('installedPayloadVerified') is True,'install-not-verified')
            save_state(journal,{'status':'active','binding':binding,'installed':installed})
            actual=platform.start();require(all(actual.get(k)==v for k,v in binding.items()),'start-binding-mismatch')
            save_state(journal,{'status':'active','binding':actual,'installed':installed})
            result['events']=validate_events(platform.collect(),actual);function_passed=True;result['installedPayloadVerified']=True
        except (ContractError,TimeoutError,OSError,ValueError) as error:result['errorType']=type(error).__name__;result['status']='failed'
        finally:
            try:cleanup=platform.cleanup()
            except (ContractError,TimeoutError,OSError,ValueError):cleanup={'confirmed':False,'appSelfCleanup':'unconfirmed'}
            confirmed=cleanup.get('confirmed') is True
            save_state(journal,{'status':'complete' if confirmed else 'cleanup-unknown','binding':locals().get('actual',binding),'installed':locals().get('installed',{}),'cleanup':cleanup})
        result.update(cleanup=cleanup,scenarioPassed=function_passed and confirmed,status='passed' if function_passed and confirmed else 'failed')
        return result

def recover(platform,state_dir,request):
    """仅收尾同一持久记录；永不签名/安装/启动，不能用删journal假装恢复。"""
    state=Path(state_dir);require(not state.is_symlink(),'state-symlink')
    with DeviceLease(state/'device.lock'):
        journal=state/'journal.json';old=read_json(read_file(journal));binding=old.get('binding',{})
        require(old.get('status') in ('active','cleanup-unknown') and set(request)=={'nonce','bundle','unsignedHapSHA256'} and all(binding.get(k)==v for k,v in request.items()),'recovery-session-mismatch')
        require(old.get('installed',{}).get('installedPayloadVerified') is True,'recovery-install-ownership-unconfirmed')
        if not platform.connected():return {'recovered':False,'deviceVerified':False,'pendingReason':'device-offline'}
        if hasattr(platform,'restore_identity'):platform.restore_identity(binding,old['installed'])
        try:cleanup=platform.cleanup()
        except (ContractError,TimeoutError,OSError,ValueError):cleanup={'confirmed':False,'appSelfCleanup':'unconfirmed'}
        success=cleanup.get('confirmed') is True
        save_state(journal,{**old,'status':'complete' if success else 'cleanup-unknown','cleanup':cleanup})
        return {'recovered':success,'cleanup':cleanup,'deviceVerified':False,'formalArtifactAllowed':False}
