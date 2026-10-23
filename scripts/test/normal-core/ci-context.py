#!/usr/bin/env python3
"""将实际 checkout 绑定到 GitHub 事件；不把 PR head 当 merge 结果。"""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def snapshot(root):
 def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
 if git('status','--porcelain','--untracked-files=no').strip():raise ValueError('tracked 工作区不干净')
 rows=[]
 for name in git('ls-files','-z').decode().split('\0'):
  if not name:continue
  path=root/name
  data=os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
  rows.append([name,hashlib.sha256(data).hexdigest()])
 return {'checkoutSHA':git('rev-parse','HEAD').decode().strip(),'treeSHA':git('rev-parse','HEAD^{tree}').decode().strip(),'trackedBytesSHA256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()}
def assert_snapshot(root,expected):
 current=snapshot(root)
 if current!=expected:raise ValueError('执行前后 HEAD/tree/tracked bytes 不一致')
 return current

def verify(root,env,event):
 def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
 def valid(value):
  if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{40}',value):raise ValueError('缺少合法提交 SHA')
  return value
 frozen=snapshot(root)
 kind=env.get('GITHUB_EVENT_NAME');expected=valid(env.get('GITHUB_SHA'));actual=git('rev-parse','HEAD');parents=git('show','-s','--format=%P','HEAD').split()
 if actual!=expected:raise ValueError('实际 checkout 与事件 SHA 不符')
 if kind not in {'pull_request','push','workflow_dispatch','merge_group'}:raise ValueError('不支持的事件')
 result={'passed':True,'event':kind,'eventSHA':expected,'checkoutSHA':actual,'treeSHA':git('rev-parse','HEAD^{tree}'),'ref':env.get('GITHUB_REF',''),'repository':env.get('GITHUB_REPOSITORY',''),'parents':parents,'trustedTarget':True,'formalArtifactAllowed':False}
 if not result['repository']:raise ValueError('缺少仓库身份')
 if kind=='pull_request':
  pr=event['pull_request'];base=valid(pr['base']['sha']);head=valid(pr['head']['sha'])
  if pr['base']['ref']!='main' or pr['base']['repo']['full_name']!=result['repository']:raise ValueError('PR base 不匹配')
  if not re.fullmatch(r'refs/pull/\d+/merge',result['ref']) or parents!=[base,head]:raise ValueError('PR 默认 merge checkout 父关系不匹配')
  result.update(baseSHA=base,headSHA=head,headRepository=pr['head']['repo']['full_name'],trustedTarget=pr['head']['repo']['full_name']==result['repository'])
 elif kind=='merge_group':
  group=event['merge_group'];base=valid(group['base_sha']);head=valid(group['head_sha'])
  if head!=actual or group['base_ref']!='refs/heads/main':raise ValueError('merge_group 身份不符')
  if subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',base,actual],capture_output=True).returncode:raise ValueError('merge_group base 不在组合祖先中')
  result.update(baseSHA=base,headSHA=head)
 result.update(frozen)
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 try:
  event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());result=verify(ROOT,os.environ,event)
 except Exception as error:result={'passed':False,'error':str(error),'formalArtifactAllowed':False}
 (args.out/'context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
