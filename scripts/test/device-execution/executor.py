#!/usr/bin/env python3
"""固定验签、短测事件与持久事务门禁；宿主替身不产生真机通过。"""
import base64
import json
import os
from pathlib import Path
import re
import stat
from controller import ContractError, DeviceLease, compare_signed_payload, digest, read_file, read_json, require

BUNDLE = 'com.yaoshining.vidalldeviceprobe'

# 只允许代码内定义的诊断枚举；禁止将平台stderr、路径、profile或密码文本写入报告。
SAFE_FAILURE_CODES=frozenset({
    'file-unavailable','file-type-or-size','file-changed-or-too-large','invalid-json','json-not-object',
    'archive-size','archive-member-count','archive-expanded-size','archive-path','archive-duplicate-member',
    'archive-special-member','archive-directory','archive-encoding','archive-member-size','archive-member-length','invalid-archive',
    'unsigned-pages-present','derived-pages-invalid','derived-pages-mismatch','derived-pages-proof',
    'sign-verify-not-complete','execution-mode-mismatch','sign-verify-command-denied',
    'verification-output-reused','official-tool-timeout','official-tool-failed',
    'certificate-pem-missing','certificate-format','signed-certificate-mismatch',
    'signed-profile-mismatch','profile-verification-failed','profile-bundle-or-type',
    'profile-validity','profile-certificate-missing','profile-certificate-mismatch',
    'profile-device-denied','approved-device-mismatch','actual-signer-mismatch',
    'signed-payload-members','signed-payload-changed','package-changed-during-verification',
    'approved-unsigned-changed','signature-not-verified','signed-package-replaced',
    'official-sign-failed','official-sign-timeout','interactive-signing-required',
    'install-semantic-failure','installed-package-identity','install-not-verified',
    'start-binding-mismatch','existing-package-not-owned','cleanup-device-offline',
    'install-ownership-unconfirmed','installed-lifecycle-changed','installation-lifecycle-unconfirmed',
    'cleanup-prestop-pid-unknown','cleanup-pid-reused-or-unknown','cleanup-prestop-pid-format',
    'events-missing-or-excessive','session-binding','event-order','event-session-mismatch','event-time','session-failed',
    'event-value','scenario-order','session-completion','runtime-not-ready','progress-not-observed','pause-not-stable',
    'seek-not-observed','render-not-observed','eof-not-observed','keep-screen-not-released','lifecycle-not-confirmed',
    'cleanup-window-deadline','cleanup-ability-present-or-unknown','cleanup-stop-unconfirmed',
    'device-disconnected-or-process-reused','session-timeout','startup-evidence-missing','too-many-device-events',
    'startup-session-mismatch','startup-time-mismatch','startup-pid-reused','pid-query-invalid','process-stat-query-failed',
    'process-stat-invalid','process-start-token','event-transfer-failed','device-not-connected','device-clock-unknown',
    'launch-failed','unexpected-preexisting-process','package-query-failed','package-list-failed','package-list-format',
    'evidence-scope','evidence-file-conflict','evidence-file-changed','evidence-size','evidence-stage','evidence-fields',
    'execution-evidence-identity-required','installed-package-unexpectedly-absent','command-timeout',
    'command-output-too-large','device-id-query-failed','device-id-format','device-id-mismatch','fresh-device-required'
})
SAFE_FAILURE_STAGES=frozenset({'preflight','sign-app','install','start','collect','cleanup','verification-output',
    'verify-app','verification-identity','verify-profile','profile-policy','actual-signer',
    'pages-derive','payload-compare','verification-final','read-events','event-validation'})

def safe_payload_diff(value):
    """诊断属性同样不可信；只重新构造有界摘要，拒绝任意名称/键/内容。"""
    if not isinstance(value,dict) or set(value)!={'schemaVersion','expectedMembers','actualMembers','differenceCount','truncated','entries'}:return None
    if value['schemaVersion']!=1 or type(value['truncated']) is not bool:return None
    if any(type(value[k]) is not int or not 0<=value[k]<=8192 for k in ['expectedMembers','actualMembers','differenceCount']):return None
    if not isinstance(value['entries'],list) or len(value['entries'])>32:return None
    result=[]
    for row in value['entries']:
        if not isinstance(row,dict):return None
        identity={'name'} if 'name' in row else {'nameSHA256','nameBytes'}
        if set(row)!=identity|{'kind','expected','actual'} or row['kind'] not in ('added','removed','changed'):return None
        if identity=={'name'}:
            if row['name'] not in ('.pages.info','module.json','ets/modules.abc'):return None
        elif not (isinstance(row['nameSHA256'],str) and re.fullmatch('[0-9a-f]{64}',row['nameSHA256']) and type(row['nameBytes']) is int and 0<row['nameBytes']<=65535):return None
        for key in ['expected','actual']:
            item=row[key]
            if item is not None and not (isinstance(item,dict) and set(item)=={'bytes','sha256'} and type(item['bytes']) is int and 0<=item['bytes']<=128*1024*1024 and isinstance(item['sha256'],str) and re.fullmatch('[0-9a-f]{64}',item['sha256'])):return None
        result.append(dict(row))
    return {**value,'entries':result}

def failure_details(error,stage):
    code=str(error) if isinstance(error,(ContractError,TimeoutError)) else None
    if isinstance(code,str) and code.startswith('event-missing-or-repeated:') and code.split(':',1)[1] in KNOWN_EVENTS:pass
    elif code not in SAFE_FAILURE_CODES:code=None
    if code is None:
        code='unclassified-contract-error' if isinstance(error,ContractError) else 'operation-timeout' if isinstance(error,TimeoutError) else 'operation-os-error' if isinstance(error,OSError) else 'operation-interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'operation-value-error'
    precise=getattr(error,'safe_stage',stage)
    detail={'stage':precise if isinstance(precise,str) and precise in SAFE_FAILURE_STAGES else stage,'code':code,'errorType':next((t.__name__ for t in (ContractError,TimeoutError,OSError,KeyboardInterrupt,SystemExit,ValueError) if isinstance(error,t)),'UnknownError')}
    exit_code=getattr(error,'safe_exit_code',None)
    if type(exit_code) is int and -255<=exit_code<=255:detail['exitCode']=exit_code
    diff=safe_payload_diff(getattr(error,'payload_diff',None))
    if diff is not None and code in ('signed-payload-members','signed-payload-changed'):detail['payloadDiff']=diff
    return detail

# 事件名称及value字段固定，不把设备提供的字符串当作可信日志。
KNOWN_EVENTS=frozenset({'session-start','runtime-ready','frame','progress','paused','resumed','seek-request','seek-complete',
    'closed','reopened','eof','release-complete','keep-screen','session-end','session-failed','release-failed',
    'keep-screen-failed','terminal','player-error','render-observed','ability-foreground','ability-background'})
APP_VALUES=frozenset({'ready','started','passed','released','new-first-frame','true','false','unconfirmed',
    'SESSION_CANCELLED','SESSION_TIMEOUT','PLAYER_ERROR','MEDIA_DURATION','POSITION_NOT_ADVANCING','FIRST_FRAME_TIMEOUT',
    'KEEP_SCREEN_NOT_ENABLED','PAUSE_NOT_STABLE','SEEK_TARGET_MISMATCH','SEEK_NOT_ADVANCING','EOF_NOT_CONFIRMED',
    'KEEP_SCREEN_NOT_RELEASED','CLEANUP_FAILED','JOURNAL_FAILED','UNEXPECTED_FAILURE','TERMINAL','observed',
    'DIAGNOSTIC_UNAVAILABLE','EOF_WITHOUT_CYCLE_DIAGNOSTIC','RUNTIME_NOT_READY','PLAYER_ALREADY_OPEN','NO_PLAYER',
    'NO_SESSION_DIRECTORY','TERMINAL_RELEASE_FORBIDDEN','REPEATED_LAUNCH','CONTENT_LOAD_FAILED',
    'DIAGNOSTICS_STALE','DIAGNOSTICS_RELEASED','PLAYER_TERMINAL','SESSION_ALREADY_ACTIVE','INVALID_LAUNCH','NONCE_REUSE','SESSION_NOT_STARTED'})
EVENT_NUMBERS=frozenset({'count','positionMs','durationMs','beforeMs','afterMs','intervalMs','targetMs','reachedMs','generation','sequence'})
CLEANUP_NAMES=frozenset({'device-id','connection-before','package-before','identity','prestop-pid','stop','pid','ability','window','uninstall','packages','connection'})

CLEANUP_CHECKS=frozenset({'device-connected','stop-command-success','ability-command-success','window-command-success',
    'uninstall-command-success','stop-semantic-success','pid-absent','ability-absent','window-absent',
    'uninstall-semantic-success','package-absent'})
CLEANUP_FAILURES=frozenset({'cleanup-device-not-connected','stop-command-failed','ability-command-failed','window-command-failed',
    'uninstall-command-failed','stop-semantic-failure','process-still-present-or-unknown','ability-still-present-or-unknown',
    'window-evidence-invalid','package-still-present-or-unknown','uninstall-semantic-failure'})

def sanitized_failure(value):
    if not isinstance(value,dict):return {'stage':'preflight','code':'unclassified-contract-error','errorType':'UnknownError'}
    code=value.get('code');known=code in SAFE_FAILURE_CODES or code in ('unclassified-contract-error','operation-timeout','operation-os-error','operation-interrupted','operation-value-error') if isinstance(code,str) else False
    if isinstance(code,str) and code.startswith('event-missing-or-repeated:'):known=code.split(':',1)[1] in KNOWN_EVENTS
    result={'stage':value.get('stage') if isinstance(value.get('stage'),str) and value.get('stage') in SAFE_FAILURE_STAGES else 'preflight',
        'code':code if known else 'unclassified-contract-error','errorType':value.get('errorType') if value.get('errorType') in ('ContractError','TimeoutError','OSError','KeyboardInterrupt','SystemExit','ValueError','UnknownError') else 'UnknownError'}
    if type(value.get('exitCode')) is int and -255<=value['exitCode']<=255:result['exitCode']=value['exitCode']
    diff=safe_payload_diff(value.get('payloadDiff'))
    if diff is not None:result['payloadDiff']=diff
    return result

WINDOW_CODES=frozenset({'ok','window-evidence-unknown','window-query-timeout','window-query-failed','window-output-invalid',
    'window-count-unrecognized','window-header-ambiguous','window-table-incomplete','window-row-unrecognized',
    'window-format-unrecognized','window-separator-unrecognized','window-section-unrecognized','window-metadata-unrecognized',
    'window-tail-unrecognized','window-integer-field','window-number-field','window-row-brackets','window-identity-field',
    'window-bundle-present','window-process-present'})

def safe_window_evidence(value):
    value=value if isinstance(value,dict) else {}
    result={'code':value.get('code') if isinstance(value.get('code'),str) and value.get('code') in WINDOW_CODES else 'window-evidence-unknown',
        'format':value.get('format') if isinstance(value.get('format'),str) and value.get('format') in ('legacy3','current25') else 'unknown'}
    for key in ['parsePassed','commandPassed','absenceConfirmed','bundleMentioned','targetProcessMentioned','rowsTruncated']:
        if type(value.get(key)) is bool:result[key]=value[key]
    for key in ['outputBytes','headerCount','totalCount','focusCount','separatorCount','reportedTotal','observedRows']:
        v=value.get(key)
        if type(v) is int and 0<=v<=2*1024*1024:result[key]=v
        elif key in ('reportedTotal','observedRows'):result[key]=None
    sha=value.get('outputSHA256')
    if isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha):result['outputSHA256']=sha
    counts=value.get('rowColumnCounts')
    if isinstance(counts,list):result['rowColumnCounts']=[n for n in counts[:64] if type(n) is int and 0<=n<=4096]
    return result

def sanitized_cleanup(value):
    value=value if isinstance(value,dict) else {}
    result={'confirmed':value.get('confirmed') is True,'appSelfCleanup':value.get('appSelfCleanup') if value.get('appSelfCleanup') in ('confirmed','unconfirmed','not-started') else 'unconfirmed'}
    checks=value.get('checks',{});result['checks']={k:v for k,v in checks.items() if k in CLEANUP_CHECKS and type(v) is bool} if isinstance(checks,dict) else {}
    reasons=value.get('failedChecks',[]);result['failedChecks']=[v for v in reasons if isinstance(v,str) and v in CLEANUP_FAILURES][:16] if isinstance(reasons,list) else []
    if 'windowEvidence' in value:result['windowEvidence']=safe_window_evidence(value['windowEvidence'])
    if value.get('deviceMutation')=='none':result['deviceMutation']='none'
    return result

def safe_event_snapshot(events,binding):
    require(isinstance(events,list) and len(events)<=2048,'events-missing-or-excessive')
    rows=[]
    for row in events:
        if not isinstance(row,dict):rows.append({'event':'unknown','invalidRow':True});continue
        name=row.get('event');out={'event':name if isinstance(name,str) and name in KNOWN_EVENTS else 'unknown'}
        out['bindingMismatch']=any(row.get(k)!=v for k,v in binding.items() if k in ('nonce','bundle','unsignedHapSHA256','pid','startedAtMs'))
        for key in ['schemaVersion','seq','cycle','elapsedMs','pid','startedAtMs']:
            value=row.get(key)
            if type(value) is int and 0<=value<10**15:out[key]=value
            elif key in row:out[key+'Invalid']=True
        if out['event']=='unknown' and isinstance(name,str):out['nameSHA256']=digest(name.encode());out['nameBytes']=len(name.encode())
        value=row.get('value')
        if isinstance(value,str):
            raw=value.encode();out['valueBytes']=len(raw);out['valueSHA256']=digest(raw)
            if value in APP_VALUES:out['value']=value
            elif len(raw)<=16384:
                try:
                    data=read_json(raw);fields={}
                    for key in EVENT_NUMBERS:
                        if key in data and numeric(data[key]):fields[key]=data[key]
                    for key in ['completed','paused']:
                        if type(data.get(key)) is bool:fields[key]=data[key]
                    if data.get('evidence')=='public-firstFrame-render-event':fields['evidence']=data['evidence']
                    if data.get('mode')=='normal-local-smoke':fields['mode']=data['mode']
                    if 'expectedUnsignedHapSHA256' in data:fields['expectedUnsignedMatches']=data['expectedUnsignedHapSHA256']==binding['unsignedHapSHA256']
                    out['fields']=fields;out['redactedFields']=len(set(data)-set(fields))
                except ContractError:out['valueRedacted']=True
            else:out['valueRedacted']=True
        else:out['valueInvalid']=True
        rows.append(out)
    return {'count':len(events),'rows':rows,'scope':'sanitized-device-events-not-raw-values'}

def safe_command_result(response=None,error=None):
    result={'timedOut':isinstance(error,TimeoutError),'interrupted':isinstance(error,(KeyboardInterrupt,SystemExit))}
    if isinstance(response,dict):
        code=response.get('returncode')
        if type(code) is int and -255<=code<=255:result['exitCode']=code
        result['timedOut']=result['timedOut'] or response.get('timedOut') is True
        for key in ['stdout','stderr']:
            value=response.get(key)
            if isinstance(value,str):data=value.encode();result[key+'Bytes']=len(data);result[key+'SHA256']=digest(data);result[key+'Empty']=not data
            else:result[key+'Unavailable']=True
    return result

class SmokeEvidence:
    """唯一nonce文件，原子更新并核前一摘要；输入只经固定白名单方法进入。"""
    def __init__(self,state,binding,execution_identity=None):
        require(set(binding)=={'nonce','bundle','unsignedHapSHA256'} and binding['bundle']==BUNDLE and re.fullmatch('[0-9a-f]{32}',binding['nonce']) and re.fullmatch('[0-9a-f]{64}',binding['unsignedHapSHA256']),'evidence-scope')
        self.state=Path(state);self.state.mkdir(mode=0o700,exist_ok=True)
        require(not self.state.is_symlink() and self.state.stat().st_uid==os.geteuid() and self.state.stat().st_mode&0o077==0,'evidence-scope')
        self.path=self.state/('smoke-'+binding['nonce']+'.json');require(not self.path.exists() and not self.path.is_symlink(),'evidence-file-conflict')
        self.expected=None;self.binding=dict(binding)
        self.data={'schemaVersion':1,'binding':dict(binding),'status':'active','scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False,'signatureVerified':False,'cleanupCommands':{},'cleanupCommandOrder':[]}
        if execution_identity is not None:
            require(set(execution_identity)=={'approvalSHA256','controllerSHA256'} and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in execution_identity.values()),'execution-evidence-identity-required')
            self.data.update(execution_identity)
        self._write()
    def _write(self):
        require(not self.path.is_symlink(),'evidence-file-changed')
        if self.expected is not None:
            st=self.path.stat();require(stat.S_ISREG(st.st_mode) and st.st_uid==os.geteuid() and st.st_nlink==1 and digest(read_file(self.path,2*1024*1024))==self.expected,'evidence-file-changed')
        else:require(not self.path.exists(),'evidence-file-conflict')
        require(len(json.dumps(self.data))<=2*1024*1024,'evidence-size');save_state(self.path,self.data);self.expected=digest(read_file(self.path,2*1024*1024))
    def checkpoint(self,stage,failure=None):
        require(stage in SAFE_FAILURE_STAGES,'evidence-stage');self.data['stage']=stage
        if failure is not None:self.data['failure']=failure_details(failure,stage)
        self._write()
    def events(self,rows,binding=None):
        self.data['events']=safe_event_snapshot(rows,binding or self.binding);self._write()
    def event_read(self,response=None,error=None):
        self.data['eventRead']=safe_command_result(response,error);self._write()
    def cleanup_command(self,name,response=None,error=None,checks=None,window=None):
        require(name in CLEANUP_NAMES,'evidence-fields');self.data['cleanupCommands'][name]=safe_command_result(response,error)
        if isinstance(checks,dict):self.data['cleanupCommands'][name]['checks']={k:v for k,v in checks.items() if k in CLEANUP_CHECKS and type(v) is bool}
        if name=='window' and window is not None:self.data['cleanupCommands'][name]['windowEvidence']=safe_window_evidence(window)
        # 重采仍保留每次固定字段/摘要，不能只覆盖最后一份窗口证据。
        safe=json.loads(json.dumps(self.data['cleanupCommands'][name]))
        self.data.setdefault('cleanupCommandHistory',[]).append({'name':name,**safe})
        if name=='window':self.data.setdefault('cleanupWindowAttempts',[]).append(safe)
        self.data['cleanupCommandOrder'].append(name);require(len(self.data['cleanupCommandOrder'])<=32,'evidence-size');self._write()
    def parse_failure(self,line,data):
        require(type(line) is int and 1<=line<=2048 and isinstance(data,bytes) and len(data)<=2*1024*1024,'evidence-fields')
        self.data['eventParseFailure']={'line':line,'bytes':len(data),'sha256':digest(data)};self._write()
    def ownership(self,**values):
        allowed={'deviceConnected','packageAbsent','transactionInstalled','installationIdentityMatched','lifecycleVerified','processMatched'}
        require(set(values)<=allowed and all(type(v) is bool for v in values.values()),'evidence-fields')
        self.data.setdefault('cleanupOwnership',{}).update(values);self._write()
    def bind_process(self,binding):
        require(all(binding.get(k)==v for k,v in self.binding.items()),'evidence-scope')
        for key in ['pid','startedAtMs','processStartTicks']:
            if key in binding:
                require(type(binding[key]) is int and 0<binding[key]<10**15,'evidence-scope');self.data['binding'][key]=binding[key]
        self._write()
    def signature(self,signature):
        safe={}
        if isinstance(signature,dict):
            for key in ['signatureVerified','payloadEqual','derivedPagesVerified']:
                if type(signature.get(key)) is bool:safe[key]=signature[key]
            for key in ['signedHAP_SHA256','unsignedHAP_SHA256','certificateDER_SHA256','profileSHA256']:
                value=signature.get(key)
                if isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value):safe[key]=value
            if type(signature.get('membersCompared')) is int and 0<=signature['membersCompared']<=8192:safe['membersCompared']=signature['membersCompared']
        self.data['signature']=safe;self.data['signatureVerified']=safe.get('signatureVerified') is True
        self.data['signatureStatus']='verified' if self.data['signatureVerified'] else 'not-completed';self._write()
    def finish(self,result,signature=None):
        self.signature(signature)
        self.data['status']=result['status'] if result.get('status') in ('passed','failed','interrupted') else 'failed'
        self.data['scenarioPassed']=result.get('scenarioPassed') is True;self.data['deviceVerified']=self.data['scenarioPassed']
        for key in ['failure','cleanupFailure','evidenceFailure']:
            if key in result:self.data[key]=sanitized_failure(result[key])
        self.data['cleanup']=sanitized_cleanup(result.get('cleanup'))
        self.data['installedPayloadVerified']=result.get('installedPayloadVerified') is True
        self._write()

def certificate_ders(data):
    """官方输出顺序没有叶子保证；解析全部PEM后按批准DER唯一匹配。"""
    blocks=re.findall(rb'-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\s]+?)\s*-----END CERTIFICATE-----',data)
    require(bool(blocks),'certificate-pem-missing')
    try: return [base64.b64decode(re.sub(rb'\s',b'',b),validate=True) for b in blocks]
    except ValueError as error: raise ContractError('certificate-format') from error

def official_ok(run,args,timeout=30):
    try: result=run([str(x) for x in args],timeout)
    except TimeoutError as error: raise ContractError('official-tool-timeout') from error
    if not (isinstance(result,dict) and type(result.get('returncode')) is int and result['returncode']==0):
        error=ContractError('official-tool-failed')
        if isinstance(result,dict):error.safe_exit_code=result.get('returncode')
        raise error
    return result

def verify_signed(unsigned,signed,config,tools,work,run,now,device_id):
    """全新私有输出；官方verify-app→verify-profile→批准身份→全payload。"""
    stage='verification-output'
    try:
        work=Path(work);require(not work.exists() and not work.is_symlink(),'verification-output-reused');work.mkdir(mode=0o700)
        before=digest(read_file(signed));unsigned_sha=digest(read_file(unsigned))
        cert=work/'cert-chain.cer';profile=work/'profile.p7b';result=work/'profile-result.json'
        stage='verify-app'
        official_ok(run,[tools['java'],'-jar',tools['signTool'],'verify-app','-inFile',signed,'-outCertChain',cert,'-outProfile',profile])
        stage='verification-identity'
        certs=[digest(d) for d in certificate_ders(read_file(cert,1024*1024))];cert_sha=config['certificateDER_SHA256']
        require(certs.count(cert_sha)==1,'signed-certificate-mismatch')
        require(digest(read_file(profile,1024*1024))==config['profileSHA256'],'signed-profile-mismatch')
        stage='verify-profile'
        official_ok(run,[tools['java'],'-jar',tools['signTool'],'verify-profile','-inFile',profile,'-outFile',result])
        verified=read_json(read_file(result,1024*1024))
        require(verified.get('verifiedPassed') is True and isinstance(verified.get('content'),dict),'profile-verification-failed')
        stage='profile-policy'
        content=verified['content'];validity=content.get('validity',{});bundle=content.get('bundle-info',{});debug=content.get('debug-info',{})
        require(content.get('type')=='debug' and bundle.get('bundle-name')==config['bundleName']==BUNDLE,'profile-bundle-or-type')
        require(type(validity.get('not-before')) is int and type(validity.get('not-after')) is int and validity['not-before']<=now<validity['not-after'],'profile-validity')
        development=bundle.get('development-certificate');require(isinstance(development,str),'profile-certificate-missing')
        require([digest(d) for d in certificate_ders(development.encode())]==[cert_sha],'profile-certificate-mismatch')
        require(debug.get('device-id-type')=='udid' and isinstance(debug.get('device-ids'),list) and device_id in debug['device-ids'],'profile-device-denied')
        require(digest(device_id.encode())==config['deviceIdSHA256'],'approved-device-mismatch')
        # 普通verify-app的证书Store并不保证首项或任意成员就是CMS signer。
        stage='actual-signer'
        signer_result=official_ok(run,[tools['java'],'-cp',tools['signerHelperClassPath']+os.pathsep+str(tools['signTool']),'ActualSigner',signed,before,cert_sha])
        signer=read_json(signer_result['stdout'].encode())
        require(signer.get('schemaVersion')==1 and signer.get('verified') is True and type(signer.get('signerCount')) is int and signer['signerCount']==1 and signer.get('signedHAP_SHA256')==before and signer.get('actualSignerDER_SHA256')==cert_sha,'actual-signer-mismatch')
        stage='pages-derive'
        # 从批准unsigned独立计算，不能从signed提取后自证；固定官方预处理参数。
        from controller import read_zip_members
        require('.pages.info' not in read_zip_members(read_file(unsigned)),'unsigned-pages-present')
        pages_file=work/'expected-pages.bin'
        derived_result=official_ok(run,[tools['java'],'-cp',tools['pagesHelperClassPath']+os.pathsep+str(tools['signTool']),'ExpectedPages',unsigned,unsigned_sha,pages_file])
        proof=read_json(derived_result['stdout'].encode());pages=read_file(pages_file,1024*1024)
        require(proof=={'schemaVersion':1,'derived':True,'unsignedHAP_SHA256':unsigned_sha,'alignment':4,'signCode':1,'pagesSHA256':digest(pages),'pagesBytes':len(pages)},'derived-pages-proof')
        require(digest(pages)==config['pagesInfoSHA256'] and len(pages)==config['pagesInfoBytes'],'derived-pages-mismatch')
        stage='payload-compare'
        comparison=compare_signed_payload(unsigned,signed,pages)
        stage='verification-final'
        require(digest(read_file(signed))==before and digest(read_file(unsigned))==unsigned_sha,'package-changed-during-verification')
        return {**{k:v for k,v in comparison.items() if k!='nextRequired'},'signatureVerified':True,'signedHAP_SHA256':before,'unsignedHAP_SHA256':unsigned_sha,'certificateDER_SHA256':cert_sha,'profileSHA256':config['profileSHA256'],'deviceVerified':False}
    except (ContractError,TimeoutError,OSError,ValueError) as error:
        error.safe_stage=stage
        raise


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

def transaction(platform,state_dir,binding,execution_identity=None):
    require(set(binding)=={'nonce','bundle','unsignedHapSHA256'},'caller-cannot-declare-process-identity')
    require(isinstance(execution_identity,dict) and set(execution_identity)=={'approvalSHA256','controllerSHA256'} and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in execution_identity.values()),'execution-evidence-identity-required')
    state=Path(state_dir);require(not state.is_symlink(),'state-symlink');state.mkdir(mode=0o700,parents=False,exist_ok=True)
    journal=state/'journal.json';used=state/'used-nonces.json'
    result={'status':'pending','scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False,'runtimeMappedLibraryHashVerified':False}
    with DeviceLease(state/'device.lock'):
        previous=read_json(read_file(journal)) if journal.exists() else {};require(previous.get('status') not in ('active','cleanup-unknown'),'pending-cleanup-journal')
        nonces=read_json(read_file(used)).get('nonces',[]) if used.exists() else [];require(binding['nonce'] not in nonces,'consumed-session-nonce')
        if not platform.connected():return {**result,'pendingReason':'device-offline'}
        if not platform.package_absent():return {**result,'pendingReason':'existing-package-not-owned'}
        evidence=SmokeEvidence(state,binding,execution_identity);platform.evidence=evidence
        save_state(used,{'nonces':[*nonces,binding['nonce']]});save_state(journal,{'status':'active','binding':binding})
        function_passed=False;interrupted=False;cleanup={'confirmed':False,'appSelfCleanup':'unconfirmed'};stage='install'
        def evidence_attempt(method,*args):
            # 证据故障不得阻止必要清理；始终让最终结果失败并保留安全错误码。
            try:return method(*args)
            except (ContractError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:
                result['evidenceFailure']=failure_details(error,stage);return None
        try:
            evidence.checkpoint(stage)
            installed=platform.install();require(installed.get('installedPayloadVerified') is True,'install-not-verified');result['installedPayloadVerified']=True
            evidence.data['installedPayloadVerified']=True;evidence.signature(getattr(platform,'verification',None))
            save_state(journal,{'status':'active','binding':binding,'installed':installed})
            stage='start';evidence.checkpoint(stage)
            actual=platform.start();require(all(actual.get(k)==v for k,v in binding.items()),'start-binding-mismatch');evidence.bind_process(actual)
            save_state(journal,{'status':'active','binding':actual,'installed':installed})
            stage='collect';evidence.checkpoint(stage);rows=platform.collect();evidence.events(rows,actual)
            stage='event-validation';evidence.checkpoint(stage);result['events']=validate_events(rows,actual);function_passed=True
        except (ContractError,TimeoutError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:
            interrupted=isinstance(error,(KeyboardInterrupt,SystemExit));result['errorType']=failure_details(error,stage)['errorType'];result['status']='interrupted' if interrupted else 'failed';result['failure']=failure_details(error,stage)
            evidence_attempt(evidence.checkpoint,stage,error)
        finally:
            stage='cleanup';evidence_attempt(evidence.signature,getattr(platform,'verification',None));evidence_attempt(evidence.checkpoint,stage)
            try:cleanup=platform.cleanup()
            except (ContractError,TimeoutError,OSError,ValueError,KeyboardInterrupt,SystemExit) as error:
                interrupted=interrupted or isinstance(error,(KeyboardInterrupt,SystemExit));cleanup={'confirmed':False,'appSelfCleanup':'unconfirmed'};result['cleanupFailure']=failure_details(error,'cleanup')
            if getattr(platform,'evidence_failure',None):result['evidenceFailure']=sanitized_failure(platform.evidence_failure)
            confirmed=cleanup.get('confirmed') is True
            passed=function_passed and confirmed and not interrupted and 'evidenceFailure' not in result
            result.update(cleanup=sanitized_cleanup(cleanup),scenarioPassed=passed,status='interrupted' if interrupted else 'passed' if passed else 'failed')
            evidence_attempt(evidence.finish,result,getattr(platform,'verification',None))
            if 'evidenceFailure' in result:
                result['scenarioPassed']=False;result['status']='interrupted' if interrupted else 'failed'
            save_state(journal,{'status':'complete' if confirmed else 'cleanup-unknown','binding':locals().get('actual',binding),'installed':locals().get('installed',{}),'cleanup':result['cleanup'],**{k:result[k] for k in ['failure','cleanupFailure','evidenceFailure'] if k in result}})
        return result

def sign_verify_transaction(platform,state_dir,binding):
    """独立签名诊断事务：不调用任何设备写入或设备清理方法。"""
    require(set(binding)=={'nonce','bundle','unsignedHapSHA256'} and re.fullmatch('[0-9a-f]{32}',binding['nonce']),'sign-verify-binding')
    state=Path(state_dir);require(not state.is_symlink(),'state-symlink');state.mkdir(mode=0o700,parents=False,exist_ok=True)
    result={'status':'pending','signatureVerified':False,'scenarioPassed':False,'deviceVerified':False,'formalArtifactAllowed':False,'deviceMutation':'none'}
    with DeviceLease(state/'device.lock'):
        journal=state/'journal.json';previous=read_json(read_file(journal)) if journal.exists() else {}
        require(previous.get('status') not in ('active','cleanup-unknown'),'pending-cleanup-journal')
        used=state/'used-nonces.json';nonces=read_json(read_file(used)).get('nonces',[]) if used.exists() else []
        require(binding['nonce'] not in nonces,'consumed-session-nonce')
        record=state/('sign-verify-'+binding['nonce']+'.json');require(not record.exists(),'sign-verify-record-exists')
        if not platform.connected():return {**result,'pendingReason':'device-offline'}
        if not platform.package_absent():return {**result,'pendingReason':'existing-package-not-owned'}
        save_state(used,{'nonces':[*nonces,binding['nonce']]})
        save_state(record,{**result,'status':'active','binding':binding})
        try:
            platform.prepare_signed()
            require(platform.verification and platform.verification.get('signatureVerified') is True,'sign-verify-not-complete')
            result.update(status='passed',signatureVerified=True)
        except (ContractError,TimeoutError,OSError,ValueError) as error:
            result.update(status='failed',failure=failure_details(error,'sign-app'))
        finally:
            identity=getattr(platform,'signed_identity',None)
            if isinstance(identity,dict) and set(identity)=={'sha256','bytes'} and re.fullmatch('[0-9a-f]{64}',str(identity['sha256'])) and type(identity['bytes']) is int and 0<identity['bytes']<=128*1024*1024:
                result['signedArtifact']=identity
            # 必须在入口finally删除临时HAP/profile之前持久化脱敏诊断。
            save_state(record,{**result,'binding':binding})
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
