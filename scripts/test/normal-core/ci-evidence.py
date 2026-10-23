#!/usr/bin/env python3
"""准备与 always 收尾；失败保持失败，只上传白名单脱敏文本。"""
import argparse,hashlib,importlib.util,json,os,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]

def verdict(needs):
 return set(needs)=={'host-contracts','target-har'} and all(v.get('result')=='success' for v in needs.values())

def finish(out,steps,mode):
 work=out/'work';public=out/'public';work.mkdir(parents=True,exist_ok=True);public.mkdir(parents=True,exist_ok=True)
 selected=[(p,Path(p.name)) for p in sorted(work.iterdir()) if p.suffix in {'.log','.json'} and p.name!='ci-status.json']
 required={'host':['context','dependencies','contracts','host'],'target':['context','target']}[mode]
 passed=all(steps.get(s,{}).get('outcome')=='success' for s in required);errors=[]
 def read(path):
  try:return json.loads(path.read_text())
  except (OSError,ValueError):return {}
 context=read(work/'context.json')
 expected={k:context.get(k) for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']}
 current=None
 try:
  spec=importlib.util.spec_from_file_location('context',HERE/'ci-context.py');identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity);current=identity.assert_snapshot(ROOT,expected)
 except (OSError,ValueError) as error:errors.append('收尾源码快照不符：'+str(error))
 if not context.get('passed') or not all(context.get(k) for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']):errors.append('缺少有效事件/源码身份')
 if mode=='host':
  if not read(work/'schema-result.json').get('passed'):errors.append('Actions schema/作用域门禁缺失或失败')
  suite=out/'suite/public';summary=read(suite/'summary.json');checks=summary.get('checks',[])
  if not summary.get('passed') or len(checks)!=47 or not all(r.get('passed') and r.get('exit')==r.get('expectedExit') for r in checks):errors.append('宿主47项检查未全部通过')
  if not (suite/'source-identities.json').is_file():errors.append('宿主源码身份缺失')
  if any(not (suite/(r.get('name','')+'.log')).is_file() for r in checks):errors.append('宿主检查日志缺失')
  for item in suite.rglob('*'):
   if item.is_symlink():raise ValueError('拒绝宿主证据符号链接')
   if item.is_file():selected.append((item,Path('host')/item.relative_to(suite)))
 else:
  target=read(work/'target-result.json')
  if not target.get('passed'):errors.append('目标构建未通过')
  expected={k:context.get(k) for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']}
  if target.get('sourceBefore')!=expected or target.get('sourceAfter')!=expected:errors.append('目标构建前后源码身份未绑定事件')
 status={'mode':mode,'sourceAfter':current,'stepsPassed':passed and not errors,'requiredSteps':required,'errors':errors,'steps':{k:{'outcome':v.get('outcome'),'conclusion':v.get('conclusion')} for k,v in steps.items()},'formalArtifactAllowed':False}
 (work/'ci-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');selected.append((work/'ci-status.json',Path('ci-status.json')))
 for source,name in selected:
  if source.is_symlink():raise ValueError('拒绝符号链接证据')
  text=source.read_text();text=re.sub(r'/(?:private/tmp|Users|Applications|home/runner|tmp|opt)/[^\s"\'<>]*','<HOST_PATH>',text)
  target=public/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
 index=[{'path':str(p.relative_to(public)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(public.rglob('*')) if p.is_file() and p!=public/'index.json']
 (public/'index.json').write_text(json.dumps({'files':index,'contextSHA256':next((r['sha256'] for r in index if r['path']=='context.json'),None),'formalArtifactAllowed':False},indent=2)+'\n')
 spec=importlib.util.spec_from_file_location('gate',HERE/'check-public.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 errors=gate.verify(public)
 if errors:raise ValueError('; '.join(errors))
 return status

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','finish','assess','verdict']);p.add_argument('--out',type=Path);p.add_argument('--mode',choices=['host','target']);args=p.parse_args()
 if args.command=='verdict':
  needs=json.loads(os.environ.get('CI_NEEDS','{}'));ok=verdict(needs);print(json.dumps({'passed':ok,'jobs':needs,'formalArtifactAllowed':False},ensure_ascii=False));return 0 if ok else 1
 if args.out is None:raise ValueError('缺少输出目录')
 if args.command=='prepare':
  args.out.mkdir(parents=True,exist_ok=False);(args.out/'work').mkdir();(args.out/'public').mkdir();return 0
 if args.command=='assess':
  status=json.loads((args.out/'public/ci-status.json').read_text());return 0 if status.get('stepsPassed') else 1
 result=finish(args.out,json.loads(os.environ.get('CI_STEPS','{}')),args.mode);print(json.dumps(result,ensure_ascii=False));return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (ValueError,OSError) as error:print('CI证据门禁失败：'+str(error),file=sys.stderr);raise SystemExit(1)
