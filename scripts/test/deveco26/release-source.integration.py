#!/usr/bin/env python3
"""仅本地：原ZIP作为模拟HTTP体，真实旧bootstrap准备/清理，不构建播放器。"""
import argparse,hashlib,importlib.util,io,json,os,shutil,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('release_local009',HERE/'release-source.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)

class Body:
 def __init__(self,stream,size,url,status=200,extra=None):
  self.stream=stream;self.remaining=size;self.status=status;self.headers={'Content-Length':str(size),**(extra or {})};self.url=url
 def geturl(self):return self.url
 def read(self,size=-1):
  size=self.remaining if size<0 else min(size,self.remaining)
  data=self.stream.read(size);self.remaining-=len(data);return data
 def close(self):self.stream.close()
 def __enter__(self):return self
 def __exit__(self,*_):self.close()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cache-source',type=Path);a=p.parse_args()
 out=M.A.safe_path(a.out);archive_path=M.A.safe_path(a.archive);before=M.A.ordinary_file(archive_path);lock,archive=M.load_inputs();M.require(before.st_size==archive['archive']['bytes'])
 out.mkdir(mode=0o700);work=out/'work';work.mkdir();start=time.monotonic();source=M.E.CONTEXT.snapshot(M.ROOT);request_summary=[];child_summary=[]
 if a.cache_source:shutil.copytree(M.A.safe_path(a.cache_source),out/'npm-cache')
 manifest={'schemaVersion':1,'archive':archive['archive'],'chunkBytes':lock['chunkBytes'],'parts':[{k:v for k,v in row.items() if k!='id'} for row in lock['parts']],'formalArtifactAllowed':False};manifest_raw=M.encoded(manifest);M.require(M.digest(manifest_raw)==lock['manifest']['sha256'])
 assets=[lock['manifest'],*lock['parts']];base=M.API+'/repos/'+M.REPOSITORY;token='LOCAL-FIXTURE-NOT-A-CREDENTIAL'
 def json_response(value,url):
  raw=M.encoded(value);return Body(io.BytesIO(raw),len(raw),url)
 def opener(req,timeout):
  url=req.full_url;headers={k.lower():v for k,v in req.header_items()};host=M.urllib.parse.urlsplit(url).hostname
  M.require(headers.get('authorization')==('Bearer '+token if host=='api.github.com' else None) and 'cookie' not in headers)
  request_summary.append({'host':host,'authorizationOnAPIOnly':True})
  if url==base:return json_response({'id':lock['repository']['id'],'full_name':M.REPOSITORY,'private':True},url)
  if url==base+'/releases/'+str(lock['release']['id']):return json_response({'id':lock['release']['id'],'tag_name':lock['release']['tag'],'target_commitish':lock['release']['targetCommit'],'immutable':True,'draft':False,'assets':[{'id':x['id'],'name':x['name'],'size':x['bytes'],'digest':'sha256:'+x['sha256'],'state':'uploaded'} for x in assets]},url)
  if url==base+'/git/ref/tags/'+lock['release']['tag']:return json_response({'ref':'refs/tags/'+lock['release']['tag'],'object':{'type':'commit','sha':lock['release']['targetCommit']}},url)
  for asset in assets:
   if url==base+'/releases/assets/'+str(asset['id']):return Body(io.BytesIO(),0,url,302,{'Location':'https://'+M.CDN+'/local/'+str(asset['id'])+'?sig=local-fixture'})
   if url=='https://'+M.CDN+'/local/'+str(asset['id'])+'?sig=local-fixture':
    if asset['id']==lock['manifest']['id']:return Body(io.BytesIO(manifest_raw),len(manifest_raw),url)
    stream=archive_path.open('rb');stream.seek(asset['offset']);return Body(stream,asset['bytes'],url)
  raise ValueError('非固定本地夹具请求')
 def runner(args,**kwargs):
  removed={M.TOKEN_KEY,'DEVECO26_ARCHIVE_URL','GH_TOKEN','GITHUB_TOKEN'};M.require(not removed.intersection(kwargs['env']))
  M.require(args[2]==str(HERE/'bootstrap.py') and args[3]=='prepare' and '--archive' in args)
  child_summary.append({'actualBootstrapInvoked':True,'checkedRemovedKeys':sorted(removed),'tokenAbsent':True,'environmentValueRecorded':False})
  return subprocess.run(args,**kwargs)
 old=os.environ.get(M.TOKEN_KEY);os.environ[M.TOKEN_KEY]=token
 result={};cleanup_exit=None;cleanup_result={};removed_dirs=[]
 try:
  result=M.prepare(out,lock,archive,source,M.GitHubTransport(token,lock,opener=opener),runner)
 finally:
  if old is None:os.environ.pop(M.TOKEN_KEY,None)
  else:os.environ[M.TOKEN_KEY]=old
  cleanup=subprocess.run([sys.executable,'-B',str(HERE/'bootstrap.py'),'cleanup','--out',str(out)],cwd=M.ROOT,capture_output=True,text=True,timeout=150)
  cleanup_exit=cleanup.returncode;(work/'local-cleanup.log').write_text(M.E.redact(cleanup.stdout+cleanup.stderr))
  if (work/'cleanup-result.json').exists():cleanup_result=json.loads((work/'cleanup-result.json').read_text())
  mount=out/'environment/mounted'
  if cleanup_exit==0 and not os.path.ismount(mount):
   for name in ['environment','npm-cache','hvigor-home']:
    path=out/name
    if path.exists():M.require(not path.is_symlink());shutil.rmtree(path);removed_dirs.append(name)
 after=M.A.ordinary_file(archive_path);same=M.A.identity(before)==M.A.identity(after)
 final={'passed':result.get('passed') is True and cleanup_exit==0 and cleanup_result.get('passed') is True and same,'networkMode':'local-original-archive-backed-mock','source':source,'actualBootstrapInvoked':bool(child_summary),'actualTargetBuildPerformed':False,'privatePATVerified':False,'remoteCISourceProofAllowed':M.proof_valid(result,source,lock,archive),'archiveBytes':result.get('archiveBytes'),'archiveSHA256':result.get('archiveSHA256'),'originalMetadataUnchanged':same,'requests':request_summary,'childEnvironment':child_summary,'cleanupExit':cleanup_exit,'cleanup':cleanup_result,'removedOwnedDirectories':removed_dirs,'sameSourceNpmCacheReused':a.cache_source is not None,'elapsedSeconds':round(time.monotonic()-start,3),'formalArtifactAllowed':False}
 (work/'local-integration.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n');print(json.dumps(final,ensure_ascii=False));return 0 if final['passed'] and not final['remoteCISourceProofAllowed'] else 1
if __name__=='__main__':raise SystemExit(main())
