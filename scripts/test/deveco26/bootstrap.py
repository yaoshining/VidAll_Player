#!/usr/bin/env python3
"""精确归档/CLI闭包准备；不安装Studio，只读挂载，仅写独立临时目录。"""
import argparse,hashlib,importlib.util,json,os,platform,re,shutil,signal,subprocess,sys,time,urllib.request,urllib.parse,urllib.error,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('evaluate',HERE/'evaluate.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E)
def failure_record(e,phase=None):
 result={'passed':False,'errorType':type(e).__name__,'formalArtifactAllowed':False}
 if phase is not None:result['phase']=phase
 if isinstance(e,urllib.error.HTTPError) and isinstance(e.code,int):result['httpStatus']=e.code
 if isinstance(e,(TimeoutError,subprocess.TimeoutExpired)) or isinstance(getattr(e,'reason',None),TimeoutError):result['timedOut']=True
 return result
def validate_url(url,allowed):
 a=urllib.parse.urlsplit(url);b=urllib.parse.urlsplit(allowed)
 if a.scheme!='https' or a.username or a.password or a.fragment or (a.netloc,a.path)!=(b.netloc,b.path):raise ValueError('下载来源不符或缺失')
def check_space(free,archive,dmg,reserve):
 if free<archive+dmg+reserve:raise ValueError('下载/解包峰值空间不足')
def copy_checked(stream,dest,size,digest):
 if not E.hash_valid(digest):raise ValueError('缺少完整hash')
 partial=dest.with_name(dest.name+'.partial');h=hashlib.sha256();count=0
 try:
  with partial.open('wb') as f:
   partial.chmod(0o600)
   while True:
    data=stream.read(1024*1024)
    if not data:break
    count+=len(data)
    if count>size:raise ValueError('响应超长')
    f.write(data);h.update(data)
  if count!=size or h.hexdigest()!=digest:raise ValueError('响应截断/摘要不符')
  partial.replace(dest)
 finally:
  if partial.exists():partial.unlink()
def fetch(url,allowed,dest,size,digest):
 validate_url(url,allowed)
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   validate_url(newurl,allowed);return super().redirect_request(req,fp,code,msg,headers,newurl)
 opener=urllib.request.build_opener(Redirect())
 with opener.open(urllib.request.Request(url,headers={'Accept-Encoding':'identity'}),timeout=30) as response:
  validate_url(response.url,allowed);E.response_identity(response.status,response.headers,size);copy_checked(response,dest,size,digest)
def extract_dmg(archive,dest,lock):
 with zipfile.ZipFile(archive) as z:
  files=[x for x in z.infolist() if not x.is_dir()]
  if len(files)!=1 or files[0].filename!=lock['member'] or files[0].file_size!=lock['bytes']:raise ValueError('ZIP成员集合不符')
  with z.open(files[0]) as stream:copy_checked(stream,dest,lock['bytes'],lock['sha256'])
class CommandFailure(ValueError):
 def __init__(self,step,returncode):
  super().__init__(step+'非零退出');self.step=step;self.returncode=returncode

def run_command(args,work,name,timeout,extra_env=None):
 try:
  result=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=timeout,cwd=HERE.parents[2],env={**os.environ,**(extra_env or {}),'HVIGOR_USER_HOME':str(E.isolated_hvigor_home(work.parent)),'NPM_CONFIG_USERCONFIG':'/dev/null','NPM_CONFIG_CACHE':str(work.parent/'npm-cache')})
 except subprocess.TimeoutExpired as e:
  text=''.join(x.decode(errors='replace') if isinstance(x,bytes) else (x or '') for x in [e.stdout,e.stderr])
  (work/(name+'.log')).write_text(E.redact(text))
  (work/(name+'.json')).write_text(json.dumps({'step':name,'exit':None,'timedOut':True})+'\n')
  raise
 (work/(name+'.log')).write_text(E.redact(result.stdout+result.stderr))
 (work/(name+'.json')).write_text(json.dumps({'step':name,'exit':result.returncode})+'\n')
 if result.returncode:raise CommandFailure(name,result.returncode)
 return result.stdout

def prepare(out,archive=None):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);stage=out/'environment';stage.mkdir(exist_ok=False);start=time.monotonic();result={'passed':False,'formalArtifactAllowed':False,'persistentSourceVerified':False}
 lock=json.loads((HERE/'archive-lock.json').read_text());tool=json.loads((HERE/'toolchain-lock.json').read_text())
 phase='resource-preflight'
 try:
  if platform.system()!='Darwin' or platform.machine()!='arm64':raise ValueError('仅支持Darwin ARM64')
  disk=shutil.disk_usage(stage);check_space(disk.free,lock['archive']['bytes'],lock['dmg']['bytes'],lock['reserveBytes']);result['diskBefore']={'free':disk.free,'total':disk.total,'reserveBytes':lock['reserveBytes']}
  result['physicalMemoryBytes']=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True,timeout=10))
  own=archive is None
  if own:
   phase='download'
   archive=stage/'studio.zip';url=os.environ.get('DEVECO26_ARCHIVE_URL','');fetch(url,lock['archive']['urlWithoutQuery'],archive,lock['archive']['bytes'],lock['archive']['sha256'])
  phase='archive-verify'
  E.verify_file(archive,lock['archive']['bytes'],lock['archive']['sha256']);result['archive']=lock['archive'];result['stage']='extract'
  phase='dmg-extract'
  dmg=stage/'studio.dmg';extract_dmg(archive,dmg,lock['dmg']);result['dmg']=lock['dmg'];result['diskAfterExtractFree']=shutil.disk_usage(stage).free
  if own:archive.unlink()
  result['stage']='mount';mount=stage/'mounted';run_command(['hdiutil','attach','-readonly','-nobrowse','-noautoopen','-mountpoint',mount,dmg],work,'mount',90)
  studio=mount/'DevEco-Studio.app';node=studio/'Contents/tools/node/bin/node'
  # 在运行任何已挂载工具前验证完整新锁；CLI尚未安装时先核Studio文件。
  phase='mounted-toolchain-verify'
  for rel,h in tool['studioFiles'].items():
   if E.sha(studio/'Contents'/rel)!=h:raise ValueError('挂载工具身份不匹配')
  result['stage']='cli-install';cli=stage/'cli';cli.mkdir();
  for name in ['package.json','package-lock.json']:shutil.copyfile(HERE/'cli'/name,cli/name)
  npm=studio/'Contents/tools/node/lib/node_modules/npm/bin/npm-cli.js'
  phase='npm-ci'
  run_command([node,npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefix',cli,'--registry=https://registry.npmjs.org','--fetch-retries=1','--fetch-retry-mintimeout=1000','--fetch-retry-maxtimeout=2000','--fetch-timeout=20000'],work,'npm-ci',600)
  wrapper=cli/'node_modules/@deveco/deveco-cli/cli.js';common=cli/'node_modules/@deveco/deveco-cli-common/dist/cli.js'
  result['stage']='cli-identity';E.preflight(studio,wrapper,common,tool,platform.machine())
  result.update(passed=True,cliLockSHA256=E.sha(HERE/'cli/package-lock.json'),diskReadyFree=shutil.disk_usage(stage).free)
  paths={'studio':str(studio),'wrapper':str(wrapper),'common':str(common)}
  (stage/'paths.json').write_text(json.dumps(paths));(stage/'paths.json').chmod(0o600)
 except Exception as e:result.update(failure_record(e,phase))
 result['elapsedSeconds']=round(time.monotonic()-start,3);(work/'bootstrap-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def verify_cleanup_tools(studio):
 lock=json.loads((HERE/'toolchain-lock.json').read_text())
 for rel in ['tools/node/bin/node','tools/hvigor/bin/hvigorw.js']:
  if E.sha(studio/'Contents'/rel)!=lock['studioFiles'][rel]:raise ValueError('cleanup工具身份不符')
def owned_daemon_pids(out):
 home=E.isolated_hvigor_home(out);p=home/'daemon/cache/daemon-sec.json'
 for component in [home/'daemon',home/'daemon/cache',p]:
  if component.is_symlink():raise ValueError('daemon registry符号链接不允许')
 if not p.exists():return set()
 data=json.loads(p.read_text());expected=set()
 if not isinstance(data,dict):raise ValueError('daemon registry格式不符')
 for item in data.values():
  if not isinstance(item,dict):raise ValueError('daemon entry格式不符')
  if Path(item.get('cwdPath','')).resolve()==HERE.parents[2].resolve():
   pid=item.get('pid')
   if type(pid) is not int or pid<=0:raise ValueError('daemon PID不符')
   expected.add(pid)
 return expected

def stopped_pids(text,expected):
 pids=[int(p) for p in re.findall(r'Stopped daemon pid (\d+)\.',text or '')]
 if any(p not in expected for p in pids):raise ValueError('停止日志PID不属于本轮project registry')
 return pids

def pid_alive(pid):
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False
 # 权限错误和其他查询失败必须传播，不能冒充进程已退出。

def wait_owned_pids(pids,deadline):
 while any(pid_alive(pid) for pid in pids):
  if time.monotonic()>=deadline:raise TimeoutError('本轮daemon未按时退出')
  time.sleep(min(.2,max(0,deadline-time.monotonic())))

def detach_bounded(mount,work,deadline):
 for attempt in range(1,6):
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('卸载总时间超限')
  name=f'unmount-{attempt:02d}'
  try:
   run_command(['hdiutil','detach',mount],work,name,min(30,remaining));return
  except CommandFailure as e:
   log=(work/(name+'.log')).read_text().lower()
   if e.returncode!=16 or not any(token in log for token in ['resource busy','device busy','资源忙']) or attempt==5:raise
   time.sleep(min(.2,max(0,deadline-time.monotonic())))

def cleanup(out):
 out=out.resolve();mount=out/'environment/mounted';work=out/'work';work.mkdir(parents=True,exist_ok=True);end=time.monotonic()+90
 if mount.exists() and os.path.ismount(mount):
  # 官方stop仅发出SIGTERM；隔离home与当前project限定作用域，随后仅查询其退出。
  pids=[]
  if (out/'environment/paths.json').is_file():
   studio=mount/'DevEco-Studio.app';verify_cleanup_tools(studio)
   node=studio/'Contents/tools/node/bin/node';env=E.child_environment(dict(os.environ),node,studio,out)
   expected=owned_daemon_pids(out)
   output=run_command([node,studio/'Contents/tools/hvigor/bin/hvigorw.js','--stop-daemon'],work,'stop-daemon',min(60,end-time.monotonic()),env)
   pids=stopped_pids(output,expected);wait_owned_pids(pids,end)
  detach_bounded(mount,work,end)
  if os.path.ismount(mount):raise ValueError('detach成功但挂载仍存在')
  (work/'cleanup-result.json').write_text(json.dumps({'passed':True,'stoppedOwnedPids':pids,'mountAbsent':True,'hvigorHomeIsolated':True,'userHOMEChanged':False,'formalArtifactAllowed':False})+'\n')

def deadline(*_):raise TimeoutError('总准备时间超限')
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cleanup']);p.add_argument('--out',type=Path,required=True);p.add_argument('--archive',type=Path);a=p.parse_args()
 signal.signal(signal.SIGALRM,deadline);signal.alarm(1200)
 if a.mode=='cleanup':cleanup(a.out);return 0
 result=prepare(a.out,a.archive);print(json.dumps({'passed':result['passed'],'errorType':result.get('errorType'),'formalArtifactAllowed':False}));return 0 if result['passed'] else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print(json.dumps(failure_record(e)));raise SystemExit(1)
