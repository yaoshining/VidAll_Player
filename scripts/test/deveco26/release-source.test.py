#!/usr/bin/env python3
"""固定私有来源：真实请求构造、流式文件、子进程环境与失败门禁。"""
import copy, hashlib, importlib.util, io, json, os, subprocess, tempfile, unittest, urllib.error
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('release_source',HERE/'release-source.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
TOKEN='test-only-secret-never-log'
SOURCE={'checkoutSHA':'a'*40,'treeSHA':'b'*40,'trackedBytesSHA256':'c'*64}
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
class Response(io.BytesIO):
 def __init__(self,body=b'',status=200,headers=None,url=''):
  super().__init__(body);self.status=status;self.headers={'Content-Length':str(len(body)),**(headers or {})};self.url=url
 def geturl(self):return self.url
class ReleaseSourceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name).resolve()/'out';self.out.mkdir();(self.out/'work').mkdir()
  self.data=b'abcdefghijk';self.archive={'archive':{'urlWithoutQuery':'https://official.example/studio.zip','bytes':len(self.data),'sha256':sha(self.data),'sha256Provenance':'测试固定输入','persistentSourceVerified':False},'dmg':{'bytes':5},'reserveBytes':3,'formalArtifactAllowed':False}
  self.lock=json.loads((HERE/'release-source-lock.json').read_text());self.lock['archiveLockSHA256']=sha(encoded(self.archive));self.lock['chunkBytes']=6
  for i,row in enumerate(self.lock['parts']):
   data=self.data[:6] if i==0 else self.data[6:];row.update(offset=0 if i==0 else 6,bytes=len(data),sha256=sha(data))
  self.manifest={'schemaVersion':1,'archive':self.archive['archive'],'chunkBytes':6,'parts':[{k:v for k,v in row.items() if k!='id'} for row in self.lock['parts']],'formalArtifactAllowed':False};self.manifest_raw=encoded(self.manifest);self.lock['manifest'].update(bytes=len(self.manifest_raw),sha256=sha(self.manifest_raw))
  self.repo={'id':1432495522,'full_name':'yaoshining/vidall-toolchain-cache','private':True}
  self.release={'id':422920456,'tag_name':self.lock['release']['tag'],'target_commitish':self.lock['release']['targetCommit'],'immutable':True,'draft':False,'assets':[{'id':a['id'],'name':a['name'],'size':a['bytes'],'digest':'sha256:'+a['sha256'],'state':'uploaded'} for a in [self.lock['manifest'],*self.lock['parts']]]}
  self.tag={'ref':'refs/tags/'+self.lock['release']['tag'],'object':{'type':'commit','sha':self.lock['release']['targetCommit']}}
  self.requests=[];self.redirect=False;self.bad_asset=None;self.inject=None;self.child_calls=[]
 def open(self,request,timeout):
  url=request.full_url;self.requests.append((url,dict(request.header_items())))
  if self.inject:return self.inject(request,timeout)
  base='https://api.github.com/repos/yaoshining/vidall-toolchain-cache'
  if url==base:return Response(encoded(self.repo),url=url)
  if url==base+'/releases/422920456':return Response(encoded(self.release),url=url)
  if url==base+'/git/ref/tags/'+self.lock['release']['tag']:return Response(encoded(self.tag),url=url)
  bodies={self.lock['manifest']['id']:self.manifest_raw,self.lock['parts'][0]['id']:self.data[:6],self.lock['parts'][1]['id']:self.data[6:]}
  for asset_id,body in bodies.items():
   api=base+'/releases/assets/'+str(asset_id);cdn='https://release-assets.githubusercontent.com/asset/'+str(asset_id)+'?sig='+TOKEN
   if url==api and self.redirect:return Response(status=302,headers={'Location':cdn},url=url)
   if url in (api,cdn):
    if self.bad_asset==asset_id:body=b'X'+body[1:]
    return Response(body,url=url)
  raise AssertionError('unexpected test URL')
 def runner(self,args,**kwargs):
  self.child_calls.append({'argCount':len(args),'envKeys':sorted(kwargs['env'])})
  child=kwargs['env'];self.assertNotIn('DEVECO26_RELEASE_READ_TOKEN',child);self.assertNotIn('DEVECO26_ARCHIVE_URL',child);self.assertNotIn('GH_TOKEN',child);self.assertNotIn('GITHUB_TOKEN',child)
  self.assertIn('--archive',args);path=Path(args[args.index('--archive')+1]);self.assertEqual(path.read_bytes(),self.data)
  (self.out/'work/bootstrap-result.json').write_text('{"passed":true}')
  return subprocess.CompletedProcess(args,0,'{"passed":true}','')
 def run_source(self,runner=None,free=10**12):
  transport=M.GitHubTransport(TOKEN,self.lock,opener=self.open)
  with patch.dict(os.environ,{'DEVECO26_RELEASE_READ_TOKEN':TOKEN,'DEVECO26_ARCHIVE_URL':'https://secret.invalid/?x='+TOKEN,'GH_TOKEN':TOKEN,'GITHUB_TOKEN':TOKEN,'TEST_SAFE_KEY':'keep'},clear=True):
   return M.prepare(self.out,self.lock,self.archive,SOURCE,transport,runner or self.runner,free_bytes=free,snapshot_check=lambda:dict(SOURCE))
 def assert_clean(self):self.assertFalse((self.out/'release-input').exists())
 def test_direct_and_redirect_success_headers_and_cleanup(self):
  self.redirect=True;r=self.run_source();self.assertTrue(r['passed']);self.assertTrue(r['ownedInputCleaned']);self.assertTrue(r['downloadVerified']);self.assertEqual(r['archiveSHA256'],sha(self.data));self.assert_clean()
  self.assertEqual(len(self.child_calls),1)
  for url,headers in self.requests:
   lower={k.lower():v for k,v in headers.items()}
   if url.startswith('https://api.github.com/'):self.assertEqual(lower.get('authorization'),'Bearer '+TOKEN)
   else:self.assertNotIn('authorization',lower);self.assertNotIn('cookie',lower)
  self.assertNotIn(TOKEN,json.dumps(r));self.assertNotIn('sig=',json.dumps(r))
 def test_private_metadata_identity_and_asset_set_fail_closed(self):
  variants=[('repo-id',lambda:self.repo.update(id=7)),('public',lambda:self.repo.update(private=False)),('repo-name',lambda:self.repo.update(full_name='other/repo')),('release-id',lambda:self.release.update(id=1)),('mutable',lambda:self.release.update(immutable=False)),('draft',lambda:self.release.update(draft=True)),('tag',lambda:self.release.update(tag_name='other')),('tag-ref',lambda:self.tag.update(ref='refs/tags/other')),('commit',lambda:self.tag['object'].update(sha='d'*40)),('asset-id',lambda:self.release['assets'][0].update(id=1)),('extra',lambda:self.release['assets'].append(copy.deepcopy(self.release['assets'][0]))),('missing',lambda:self.release['assets'].pop()),('digest',lambda:self.release['assets'][0].update(digest='sha256:'+'0'*64)),('state',lambda:self.release['assets'][0].update(state='starter'))]
  initial=copy.deepcopy((self.repo,self.release,self.tag))
  for name,mutation in variants:
   self.repo,self.release,self.tag=copy.deepcopy(initial);mutation()
   with self.subTest(name=name):self.assertFalse(self.run_source()['passed']);self.assert_clean()
  self.assertFalse(self.child_calls)
 def test_bad_manifest_cannot_redefine_archive_or_layout(self):
  base=copy.deepcopy(self.manifest)
  for mode in ['sha','order','offset','duplicate','path','full-hash','chunk']:
   self.manifest=copy.deepcopy(base)
   if mode=='order':self.manifest['parts'].reverse()
   elif mode=='offset':self.manifest['parts'][1]['offset']=0
   elif mode=='duplicate':self.manifest['parts'][1]=self.manifest['parts'][0]
   elif mode=='path':self.manifest['parts'][0]['name']='../escape'
   elif mode=='full-hash':self.manifest['archive']['sha256']='0'*64
   elif mode=='chunk':self.manifest['chunkBytes']=7
   self.manifest_raw=encoded(self.manifest)
   if mode!='sha':self.lock['manifest'].update(bytes=len(self.manifest_raw),sha256=sha(self.manifest_raw));self.release['assets'][0].update(size=len(self.manifest_raw),digest='sha256:'+sha(self.manifest_raw))
   else:self.manifest_raw+=b' '
   with self.subTest(mode=mode):self.assertFalse(self.run_source()['passed']);self.assert_clean()
 def test_bad_part_and_wrong_full_hash_cleanup(self):
  self.bad_asset=self.lock['parts'][1]['id'];r=self.run_source();self.assertFalse(r['passed']);self.assert_clean();self.assertFalse(self.child_calls)
  self.bad_asset=None;self.archive['archive']['sha256']='0'*64;self.manifest['archive']['sha256']='0'*64;self.manifest_raw=encoded(self.manifest);self.lock['manifest'].update(bytes=len(self.manifest_raw),sha256=sha(self.manifest_raw));self.release['assets'][0].update(size=len(self.manifest_raw),digest='sha256:'+sha(self.manifest_raw))
  self.assertFalse(self.run_source()['passed']);self.assert_clean()
 def test_truncated_oversized_and_interrupted_body(self):
  base=self.open
  for mode in ['truncated','oversized','interrupted']:
   def altered(req,timeout):
    self.inject=None
    try:resp=base(req,timeout)
    finally:self.inject=altered
    if req.full_url.endswith('/'+str(self.lock['parts'][1]['id'])):
     if mode=='truncated':return Response(b'ab',headers={'Content-Length':'5'},url=req.full_url)
     if mode=='oversized':return Response(b'abcdef',headers={'Content-Length':'5'},url=req.full_url)
     class Broken(Response):
      def read(self,n=-1):raise TimeoutError('sig='+TOKEN)
     return Broken(b'abcde',url=req.full_url)
    return resp
   self.inject=altered
   with self.subTest(mode=mode):r=self.run_source();self.assertFalse(r['passed']);self.assert_clean();self.assertNotIn(TOKEN,json.dumps(r))
  self.inject=None
 def test_auth_http_and_redirect_errors_are_sanitized(self):
  for status in [401,403,404,500]:
   self.inject=lambda req,timeout:Response(b'error '+TOKEN.encode(),status=status,url=req.full_url)
   r=self.run_source();self.assertFalse(r['passed']);self.assertEqual(r['httpStatus'],status);self.assertNotIn(TOKEN,json.dumps(r));self.assert_clean()
  for url in ['http://release-assets.githubusercontent.com/a','https://evil.example/a?x='+TOKEN,'https://api.github.com@evil.example/a','https://release-assets.githubusercontent.com.evil/a','https://release-assets.githubusercontent.com:444/a','https://release-assets.githubusercontent.com/a#secret']:
   self.inject=lambda req,timeout:Response(status=302,headers={'Location':url},url=req.full_url)
   r=self.run_source();self.assertFalse(r['passed']);self.assertNotIn(TOKEN,json.dumps(r));self.assert_clean()
 def test_metadata_must_not_redirect_or_exceed_limit(self):
  for response in [Response(status=302,headers={'Location':'https://release-assets.githubusercontent.com/x'}),Response(b'{}',headers={'Content-Length':'99999999'})]:
   self.inject=lambda req,timeout:response
   self.assertFalse(self.run_source()['passed']);self.assert_clean()
 def test_chunked_metadata_without_length_is_bounded_and_allowed(self):
  base=self.open
  def chunked(req,timeout):
   self.inject=None
   try:response=base(req,timeout)
   finally:self.inject=chunked
   if '/releases/assets/' not in req.full_url:response.headers.pop('Content-Length',None)
   return response
  self.inject=chunked;self.assertTrue(self.run_source()['passed']);self.assert_clean()
 def test_binary_response_still_requires_exact_content_length(self):
  base=self.open
  def missing(req,timeout):
   self.inject=None
   try:response=base(req,timeout)
   finally:self.inject=missing
   if '/releases/assets/' in req.full_url:response.headers.pop('Content-Length',None)
   return response
  self.inject=missing;self.assertFalse(self.run_source()['passed']);self.assert_clean()
 def test_insufficient_space_rejected_before_network(self):
  needed=M.required_space(self.lock,self.archive)
  self.assertEqual(needed,2*len(self.data)+5+3+2147483648)
  self.assertFalse(self.run_source(free=needed-1)['passed']);self.assertFalse(self.requests);self.assert_clean()
 def test_existing_and_symlink_input_not_deleted(self):
  owned=self.out/'release-input';owned.mkdir();keep=owned/'mine';keep.write_text('keep')
  self.assertFalse(self.run_source()['passed']);self.assertEqual(keep.read_text(),'keep');keep.unlink();owned.rmdir()
  other=self.out/'other';other.mkdir();(other/'mine').write_text('keep');owned.symlink_to(other,target_is_directory=True)
  self.assertFalse(self.run_source()['passed']);self.assertEqual((other/'mine').read_text(),'keep')
 def test_child_failure_timeout_and_secret_redaction(self):
  for mode in ['exit','timeout','fake-success']:
   def failed(args,**kwargs):
    if mode=='timeout':raise subprocess.TimeoutExpired(args,1,output=TOKEN)
    if mode=='fake-success':return subprocess.CompletedProcess(args,0,TOKEN,TOKEN)
    return subprocess.CompletedProcess(args,7,TOKEN,TOKEN)
   with self.subTest(mode=mode):r=self.run_source(runner=failed);self.assertFalse(r['passed']);self.assert_clean();self.assertNotIn(TOKEN,json.dumps(r));self.assertNotIn(TOKEN,(self.out/'work/release-source-bootstrap.log').read_text() if (self.out/'work/release-source-bootstrap.log').exists() else '')
 def test_foreign_file_during_cleanup_is_preserved_and_failed(self):
  def changed(args,**kwargs):
   result=self.runner(args,**kwargs);(self.out/'release-input/foreign').write_text('keep');return result
  r=self.run_source(runner=changed);self.assertFalse(r['passed']);self.assertFalse(r['ownedInputCleaned']);self.assertEqual((self.out/'release-input/foreign').read_text(),'keep')
 def test_empty_or_control_character_token_rejected(self):
  for value in ['', ' ', 'x\ny']:
   with self.subTest(value=value),self.assertRaises(ValueError):M.GitHubTransport(value,self.lock,opener=self.open)
 def test_real_http_error_redirect_and_permission_body(self):
  base=self.open
  def redirect(req,timeout):
   if '/releases/assets/' in req.full_url:
    asset_id=req.full_url.rsplit('/',1)[-1]
    raise urllib.error.HTTPError(req.full_url,302,TOKEN,{'Location':'https://release-assets.githubusercontent.com/asset/'+asset_id+'?sig='+TOKEN},io.BytesIO())
   self.inject=None
   try:return base(req,timeout)
   finally:self.inject=redirect
  self.inject=redirect;r=self.run_source();self.assertTrue(r['passed']);self.assert_clean()
  (self.out/'work/bootstrap-result.json').unlink()
  def denied(req,timeout):raise urllib.error.HTTPError(req.full_url,401,TOKEN,{},io.BytesIO(TOKEN.encode()))
  self.inject=denied;r=self.run_source();self.assertFalse(r['passed']);self.assertEqual(r['httpStatus'],401);self.assertNotIn(TOKEN,json.dumps(r))
  self.assertIsNone(M.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))
 def test_existing_bootstrap_evidence_cannot_green_empty_child(self):
  old=self.out/'work/bootstrap-result.json';old.write_text('{"passed":true}')
  r=self.run_source(runner=lambda *a,**kw:subprocess.CompletedProcess(a,0,'',''))
  self.assertFalse(r['passed']);self.assertEqual(old.read_text(),'{"passed":true}');self.assertFalse(self.requests);self.assert_clean()
 def test_injected_transport_not_accepted_as_remote_ci_proof(self):
  r=self.run_source();self.assertTrue(r['passed']);self.assertFalse(M.proof_valid(r,SOURCE,self.lock,self.archive))
 def test_source_proof_requires_locks_identity_and_owned_cleanup(self):
  r=self.run_source();self.assertEqual(r['transportMode'],'injected-test-transport');r['transportMode']='github-api' # 仅构造CI证明的单元测试夹具
  self.assertTrue(M.proof_valid(r,SOURCE,self.lock,self.archive))
  for key,value in [('ownedInputCleaned',False),('downloadVerified',False),('bootstrapPassed',False),('sourceLockSHA256','0'*64),('archiveSHA256','0'*64),('sourceAfter',{})]:
   bad=copy.deepcopy(r);bad[key]=value
   with self.subTest(key=key):self.assertFalse(M.proof_valid(bad,SOURCE,self.lock,self.archive))
if __name__=='__main__':unittest.main()
