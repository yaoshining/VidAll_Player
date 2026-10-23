#!/usr/bin/env python3
"""使用固定官方 actionlint 检查全部工作流及真实作用域负例，不执行工作流。"""
import argparse,hashlib,importlib.util,json,platform,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def platform_key(system,machine):
 mapping={('Darwin','arm64'):'darwin_arm64',('Linux','x86_64'):'linux_amd64'}
 if (system,machine) not in mapping:raise ValueError('未锁定的actionlint宿主平台')
 return mapping[system,machine]
def extract_verified(archive,expected,target):
 if digest(archive)!=expected:raise ValueError('actionlint归档摘要不符')
 with tarfile.open(archive,'r:gz') as tar:
  matches=[m for m in tar.getmembers() if m.name=='actionlint']
  if len(matches)!=1 or not matches[0].isreg() or matches[0].size>30*1024*1024:raise ValueError('actionlint成员缺失/重复/特殊类型')
  data=tar.extractfile(matches[0]).read()
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(0o755);return target

def run(root,out,archive=None):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);tools=work/'schema-tool';tools.mkdir(exist_ok=True)
 lock=json.loads((HERE/'ci-schema-lock.json').read_text());key=platform_key(platform.system(),platform.machine());entry=lock['archives'][key];result={'passed':False,'version':lock['version'],'platform':key,'commands':[],'formalArtifactAllowed':False}
 spec=importlib.util.spec_from_file_location('target',HERE/'ci-target.py');target=importlib.util.module_from_spec(spec);spec.loader.exec_module(target)
 import os
 def command(name,args):return target.command('schema-'+name,args,root,dict(os.environ),work,result['commands'],120)
 try:
  if archive is None:
   archive=tools/entry['name'];url='https://github.com/rhysd/actionlint/releases/download/v'+lock['version']+'/'+entry['name']
   command('download',['curl','--fail','--silent','--show-error','--retry','3','--location',url,'--output',archive])
  tool=extract_verified(archive,entry['sha256'],tools/'actionlint');version=command('version',[tool,'-version'])
  if version.splitlines()[0]!=lock['version']:raise ValueError('actionlint实际版本不符')
  result.update(archiveSHA256=digest(archive),binarySHA256=digest(tool))
  files=sorted((root/'.github/workflows').glob('*.yml'))+sorted((root/'.github/workflows').glob('*.yaml'))
  if not files:raise ValueError('没有工作流文件')
  config=root/'.github/actionlint.yaml';args=[tool,'-shellcheck=','-pyflakes=','-config-file',config]
  command('all',[*args,*files]);result['workflows']={str(p.relative_to(root)):digest(p) for p in files};result['configSHA256']=digest(config)
  # 外部ShellCheck/Pyflakes不在本门禁范围；Actions schema/表达式规则没有忽略项。
  original=(root/'.github/workflows/normal-core.yml').read_text()
  mutants={'job-env-runner':(original.replace('    timeout-minutes: 15\n','    timeout-minutes: 15\n    env:\n      CONTEXT_NEGATIVE: ${{ runner.temp }}\n',1),'runner'), 'job-if-steps':(original.replace("    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository", "    if: steps.missing.outcome == 'success'",1),'steps')}
  checks=[]
  for name,(text,context) in mutants.items():
   if text==original:raise ValueError('作用域变异未生效')
   file=tools/(name+'.yml');file.write_text(text)
   try:command(name,[*args,file])
   except RuntimeError:pass
   row=result['commands'][-1];log=(work/('schema-'+name+'.log')).read_text();accepted=row['exit']==1 and ('context "'+context+'" is not allowed here') in log
   row['expectedExit']=1;row['acceptedAsNegative']=accepted;checks.append({'name':name,'rejectedForExpectedContext':accepted})
  if not all(c['rejectedForExpectedContext'] for c in checks):raise ValueError('作用域负例未被实际解析器拒绝')
  result.update(passed=True,scopeMutations=checks)
 except Exception as error:result['error']=str(error)
 (work/'schema-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--archive',type=Path);args=p.parse_args();result=run(ROOT,args.out,args.archive);print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
