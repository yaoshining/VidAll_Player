#!/usr/bin/env python3
"""固定私有 Release 的传输包装器；旧 bootstrap/工具链锁保持不变。"""
import argparse, hashlib, importlib.util, json, os, re, shutil, stat, subprocess, sys, time
from pathlib import Path
import urllib.error, urllib.parse, urllib.request
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
API='https://api.github.com'
REPOSITORY='yaoshining/vidall-toolchain-cache'
CDN='release-assets.githubusercontent.com'
TOKEN_KEY='DEVECO26_RELEASE_READ_TOKEN'
SOURCE_LOCK=HERE/'release-source-lock.json'
ARCHIVE_LOCK=HERE/'archive-lock.json'
BLOCK=1024*1024

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
B=module('bootstrap009',HERE/'bootstrap.py')
E=B.E
A=module('assets009',HERE.parent/'deveco26-assets/prepare.py')

def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def digest(value):return hashlib.sha256(value).hexdigest()
def require(condition):
 if not condition:raise ValueError('固定来源校验不符')
def config_sha(lock):return digest(encoded(lock))
def required_space(lock,archive):return 2*archive['archive']['bytes']+archive['dmg']['bytes']+archive['reserveBytes']+lock['buildReserveBytes']
def validate_config(lock,archive):
 require(lock['schemaVersion']==1 and lock['formalArtifactAllowed'] is False)
 require(lock['repository']['fullName']==REPOSITORY and lock['repository']['private'] is True and type(lock['repository']['id']) is int)
 require(lock['cdnHost']==CDN and lock['release']['immutable'] is True and re.fullmatch('[0-9a-f]{40}',lock['release']['targetCommit']))
 require(re.fullmatch('[A-Za-z0-9._-]+',lock['release']['tag']) is not None)
 require(lock['archiveLockSHA256']==digest(encoded(archive)))
 require(type(lock['buildReserveBytes']) is int and lock['buildReserveBytes']>=2147483648)
 sizes=A.layout(archive['archive']['bytes'],lock['chunkBytes']);require(len(sizes)==len(lock['parts']))
 assets=[lock['manifest'],*lock['parts']];require(len({a['id'] for a in assets})==len(assets))
 for a in assets:require(type(a['id']) is int and a['id']>0 and type(a['bytes']) is int and a['bytes']>0 and E.hash_valid(a['sha256']))
 require(lock['manifest']['name']=='deveco26-archive-manifest.json' and lock['manifest']['bytes']<=65536)
 offset=0
 for i,(size,row) in enumerate(zip(sizes,lock['parts']),1):
  require({k:row[k] for k in ['ordinal','name','offset','bytes']}==dict(ordinal=i,name=f'studio26.zip.part{i:03d}',offset=offset,bytes=size));offset+=size

def load_inputs():
 raw=SOURCE_LOCK.read_bytes();lock=json.loads(raw,object_pairs_hook=A.unique_object);archive_raw=ARCHIVE_LOCK.read_bytes();archive=json.loads(archive_raw,object_pairs_hook=A.unique_object)
 require(raw==encoded(lock) and archive_raw==encoded(archive));validate_config(lock,archive);return lock,archive

class HTTPFailure(ValueError):
 def __init__(self,status):super().__init__('固定来源HTTP失败');self.http_status=status
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
class GitHubTransport:
 def __init__(self,token,lock,opener=None):
  require(isinstance(token,str) and bool(token.strip()) and token==token.strip() and not any(ord(c)<33 or ord(c)>126 for c in token))
  self.token=token;self.lock=lock;self.mode='injected-test-transport' if opener is not None else 'github-api';self.open=opener or urllib.request.build_opener(NoRedirect()).open
 def request(self,url,api=True,accept='application/vnd.github+json'):
  parsed=urllib.parse.urlsplit(url)
  require(parsed.scheme=='https' and parsed.netloc==('api.github.com' if api else CDN) and not parsed.fragment and not parsed.username and not parsed.password)
  if api:require(not parsed.query and (parsed.path.startswith('/repos/'+REPOSITORY+'/') or parsed.path=='/repos/'+REPOSITORY))
  headers={'Accept':accept,'Accept-Encoding':'identity','User-Agent':'VidAll-locked-source','X-GitHub-Api-Version':'2026-03-10'}
  if api:headers['Authorization']='Bearer '+self.token
  try:response=self.open(urllib.request.Request(url,headers=headers),timeout=30)
  except urllib.error.HTTPError as error:response=error
  final=response.geturl()
  if final and final!=url:response.close();raise ValueError('隐式重定向被拒绝')
  return response
 def metadata(self,path):
  with self.request(API+path) as response:
   if response.status!=200:raise HTTPFailure(response.status)
   declared=response.headers.get('Content-Length');limit=2*1024*1024
   if declared is not None:require(0<=int(declared)<=limit)
   raw=response.read(limit+1);require(len(raw)<=limit)
   if declared is not None:require(len(raw)==int(declared))
   return json.loads(raw,object_pairs_hook=A.unique_object)
 def asset(self,asset):
  response=self.request(API+'/repos/'+REPOSITORY+'/releases/assets/'+str(asset['id']),accept='application/octet-stream')
  if response.status==302:
   location=response.headers.get('Location','');response.close()
   require(isinstance(location,str) and 0<len(location)<=8192 and not any(ord(c)<33 for c in location))
   # 新请求仅携带公开HTTP头；Authorization从不发送至资产CDN。
   response=self.request(location,api=False,accept='application/octet-stream')
  if response.status!=200:
   status=response.status;response.close();raise HTTPFailure(status)
  try:E.response_identity(response.status,response.headers,asset['bytes']);require(response.headers.get('Content-Encoding','identity')=='identity')
  except BaseException:response.close();raise
  return response

def metadata_verified(transport,lock):
 base='/repos/'+REPOSITORY;repo=transport.metadata(base);release=transport.metadata(base+'/releases/'+str(lock['release']['id']));tag=transport.metadata(base+'/git/ref/tags/'+lock['release']['tag'])
 require(repo.get('id')==lock['repository']['id'] and repo.get('full_name')==REPOSITORY and repo.get('private') is True)
 require(release.get('id')==lock['release']['id'] and release.get('tag_name')==lock['release']['tag'] and release.get('target_commitish')==lock['release']['targetCommit'] and release.get('immutable') is True and release.get('draft') is False)
 require(tag.get('ref')=='refs/tags/'+lock['release']['tag'] and tag.get('object',{}).get('type')=='commit' and tag.get('object',{}).get('sha')==lock['release']['targetCommit'])
 actual=release.get('assets');expected=[lock['manifest'],*lock['parts']];require(isinstance(actual,list) and len(actual)==len(expected))
 for item in expected:
  rows=[a for a in actual if a.get('id')==item['id']];require(len(rows)==1);a=rows[0]
  require(a.get('name')==item['name'] and a.get('size')==item['bytes'] and a.get('digest')=='sha256:'+item['sha256'] and a.get('state')=='uploaded')

def manifest_verified(raw,lock,archive):
 require(len(raw)==lock['manifest']['bytes'] and digest(raw)==lock['manifest']['sha256'])
 actual=json.loads(raw,object_pairs_hook=A.unique_object)
 expected={'schemaVersion':1,'archive':archive['archive'],'chunkBytes':lock['chunkBytes'],'parts':[{k:v for k,v in p.items() if k!='id'} for p in lock['parts']],'formalArtifactAllowed':False}
 require(actual==expected)

def input_cleanup(directory,owner,files):
 if owner is None:return True
 try:
  require(not directory.is_symlink() and (directory.stat().st_dev,directory.stat().st_ino)==owner)
  require({p.name for p in directory.iterdir()}==set(files))
  for name,expected in files.items():
   p=directory/name;require(not p.is_symlink() and p.is_file() and (p.stat().st_dev,p.stat().st_ino)==expected)
  for name in files:(directory/name).unlink()
  directory.rmdir();return True
 except (OSError,ValueError):return False

def expected_identity(lock):
 return {'repository':lock['repository'],'release':lock['release'],'manifest':lock['manifest'],'parts':lock['parts']}
def proof_valid(result,source,lock,archive):
 try:
  return result.get('transportMode')=='github-api' and all(result.get(k) is True for k in ['passed','metadataVerified','manifestVerified','downloadVerified','bootstrapPassed','ownedInputCleaned']) and result.get('sourceBefore')==source==result.get('sourceAfter') and result.get('sourceLockSHA256')==config_sha(lock) and result.get('archiveLockSHA256')==lock['archiveLockSHA256'] and result.get('sourceIdentity')==expected_identity(lock) and result.get('archiveBytes')==archive['archive']['bytes'] and result.get('archiveSHA256')==archive['archive']['sha256']
 except (KeyError,TypeError):return False

def prepare(out,lock,archive,source,transport,runner=subprocess.run,free_bytes=None,snapshot_check=None):
 out=A.safe_path(out);work=A.safe_path(out/'work');require(work.is_dir())
 owned=out/'release-input';owner=None;files={};phase='preflight';start=time.monotonic()
 result={'passed':False,'transportMode':transport.mode,'metadataVerified':False,'manifestVerified':False,'downloadVerified':False,'bootstrapPassed':False,'ownedInputCleaned':False,'sourceBefore':source,'sourceAfter':None,'sourceLockSHA256':config_sha(lock),'archiveLockSHA256':lock['archiveLockSHA256'],'sourceIdentity':expected_identity(lock),'formalArtifactAllowed':False,'officialPersistentSourceVerified':False}
 try:
  validate_config(lock,archive);required=required_space(lock,archive);free=shutil.disk_usage(out).free if free_bytes is None else free_bytes;result.update(requiredFreeBytes=required,diskBeforeFreeBytes=free);require(free>=required)
  require(not (work/'bootstrap-result.json').exists());A.safe_path(owned);owned.mkdir(mode=0o700);owner=(owned.stat().st_dev,owned.stat().st_ino)
  phase='metadata';metadata_verified(transport,lock);result['metadataVerified']=True
  phase='manifest'
  with transport.asset(lock['manifest']) as response:raw=response.read(lock['manifest']['bytes']+1)
  manifest_verified(raw,lock,archive);result['manifestVerified']=True
  phase='parts';partial=owned/'studio.zip.partial';whole=hashlib.sha256();count=0
  with os.fdopen(os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as output:
   info=os.fstat(output.fileno());files[partial.name]=(info.st_dev,info.st_ino)
   for asset in lock['parts']:
    part=hashlib.sha256();received=0
    with transport.asset(asset) as response:
     while data:=response.read(BLOCK):
      received+=len(data);require(received<=asset['bytes']);output.write(data);whole.update(data);part.update(data);count+=len(data)
    require(received==asset['bytes'] and part.hexdigest()==asset['sha256'])
   output.flush();os.fsync(output.fileno())
  require(count==archive['archive']['bytes'] and whole.hexdigest()==archive['archive']['sha256'])
  target=owned/'studio.zip';partial.rename(target);files[target.name]=files.pop(partial.name);result.update(downloadVerified=True,archiveBytes=count,archiveSHA256=whole.hexdigest())
  phase='bootstrap';child={k:v for k,v in os.environ.items() if k not in {TOKEN_KEY,'DEVECO26_ARCHIVE_URL','GH_TOKEN','GITHUB_TOKEN'}}
  args=[sys.executable,'-B',str(HERE/'bootstrap.py'),'prepare','--out',str(out),'--archive',str(target)]
  completed=runner(args,cwd=ROOT,env=child,capture_output=True,text=True,timeout=1200)
  text=(completed.stdout or '')+(completed.stderr or '');text=text.replace(transport.token,'<REDACTED>');(work/'release-source-bootstrap.log').write_text(E.redact(text))
  result['bootstrapExit']=completed.returncode;require(completed.returncode==0)
  result['bootstrapPassed']=json.loads((work/'bootstrap-result.json').read_text()).get('passed') is True;require(result['bootstrapPassed'])
  result['sourceAfter']=(snapshot_check or (lambda:E.CONTEXT.assert_snapshot(ROOT,source)))();require(result['sourceAfter']==source)
  result['passed']=True
 except Exception as error:
  result.update(B.failure_record(error,phase))
  if isinstance(error,HTTPFailure):result['httpStatus']=error.http_status
 finally:
  result['ownedInputCleaned']=input_cleanup(owned,owner,files)
  result['passed']=result['passed'] and result['ownedInputCleaned'];result['elapsedSeconds']=round(time.monotonic()-start,3)
  (work/'release-source-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 try:
  lock,archive=load_inputs();context=json.loads((args.out/'work/context.json').read_text());source={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']};require(context.get('passed') is True);E.CONTEXT.assert_snapshot(ROOT,source)
  transport=GitHubTransport(os.environ.get(TOKEN_KEY,''),lock);result=prepare(args.out,lock,archive,source,transport);print(json.dumps({'passed':result['passed'],'phase':result.get('phase'),'errorType':result.get('errorType'),'formalArtifactAllowed':False}));return 0 if result['passed'] else 1
 except Exception as error:print(json.dumps(B.failure_record(error,'entry')));return 1
if __name__=='__main__':raise SystemExit(main())
