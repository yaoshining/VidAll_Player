#!/usr/bin/env python3
"""新profile组合；拒绝缺consumer、错误事件和未批准target，不改变旧组合。"""
import argparse,importlib.util,json,os,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
s=importlib.util.spec_from_file_location('evaluate007',HERE.parent/'deveco26/evaluate.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E)
def identity(data):
 return isinstance(data,dict) and set(data)=={'checkoutSHA','treeSHA','trackedBytesSHA256'} and all(isinstance(data.get(k),str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',data[k]) for k,n in [('checkoutSHA',40),('treeSHA',40),('trackedBytesSHA256',64)])
def trusted(context,approved):
 sha=context.get('checkoutSHA','')
 return bool(re.fullmatch('[0-9a-f]{40}',sha) and approved==sha==context.get('eventSHA') and context.get('passed') is True and context.get('trustedTarget') is True and context.get('repository')=='yaoshining/VidAll_Player' and context.get('event') in {'pull_request','push','merge_group'} and (context.get('event')!='pull_request' or context.get('headRepository')==context['repository']))
def verdict(needs,expected):
 try:
  if set(needs)!={'host-contracts','target-har'} or any(v.get('result')!='success' for v in needs.values()):return False
  source=json.loads(needs['host-contracts']['outputs']['source']);summary=json.loads(needs['target-har']['outputs']['summary'])
  return identity(source) and source['checkoutSHA']==expected and summary.get('source')==source and all(summary.get(k) is True for k in ['passed','targetPassed','consumerPassed','cleanupPassed','apiNegativePassed'])
 except (KeyError,TypeError,ValueError):return False

def output(key,value):
 path=os.environ.get('GITHUB_OUTPUT')
 if path:
  with open(path,'a') as f:f.write(key+'='+json.dumps(value,separators=(',',':'))+'\n')
def finish(out,steps):
 work=out/'work'
 def read(name):
  try:return json.loads((work/name).read_text())
  except (OSError,ValueError):return {}
 context=read('context.json');target=read('evaluation-result.json');consumer=read('consumer-result.json');negative=read('consumer-negative-result.json');source={k:context.get(k) for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']};valid=False
 try:valid=identity(source) and E.CONTEXT.assert_snapshot(ROOT,source)==source
 except (ValueError,OSError):pass
 target_ok=target.get('passed') is True and target.get('sourceBefore')==source==target.get('sourceAfter')
 consumer_ok=consumer.get('passed') is True and consumer.get('sourceBefore')==source==consumer.get('sourceAfter') and consumer.get('inputHAR')==target.get('artifact',{}).get('harSHA256') and consumer.get('libraries')==target.get('artifact',{}).get('libraries') and consumer.get('artifact',{}).get('passed') is True
 cleanup_ok=consumer.get('cleanup',{}).get('passed') is True and read('cleanup-result.json').get('passed') is True
 negative_ok=negative.get('passed') is True and negative.get('specificArkTSDiagnostic') is True and negative.get('cleanup',{}).get('passed') is True and negative.get('sourceBefore')==source==negative.get('sourceAfter')
 required=['context','trust','bootstrap','runtime','target','api_negative','consumer','cleanup'];steps_ok=all(steps.get(k,{}).get('outcome')=='success' for k in required)
 summary={'passed':valid and target_ok and consumer_ok and cleanup_ok and negative_ok and steps_ok,'targetPassed':target_ok,'consumerPassed':consumer_ok,'cleanupPassed':cleanup_ok,'apiNegativePassed':negative_ok,'source':source,'formalArtifactAllowed':False}
 (work/'gate-summary.json').write_text(json.dumps(summary,indent=2)+'\n');status=E.publish(ROOT,out,summary['passed'])
 if not status['passed'] and summary['passed']:
  summary['passed']=False;(work/'gate-summary.json').write_text(json.dumps(summary,indent=2)+'\n');E.publish(ROOT,out,False)
 output('summary',summary);return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['trust','host-output','finish','assess','verdict']);p.add_argument('--out',type=Path);a=p.parse_args()
 if a.mode=='verdict':return 0 if verdict(json.loads(os.environ.get('CI_NEEDS','{}')),os.environ.get('GITHUB_SHA','')) else 1
 if a.mode=='finish':finish(a.out,json.loads(os.environ.get('CI_STEPS','{}')));return 0
 if a.mode=='assess':return 0 if json.loads((a.out/'public/gate-summary.json').read_text()).get('passed') else 1
 context=json.loads((a.out/'work/context.json').read_text());source={k:context[k] for k in ['checkoutSHA','treeSHA','trackedBytesSHA256']};E.CONTEXT.assert_snapshot(ROOT,source)
 if a.mode=='trust':
  good=trusted(context,os.environ.get('DEVECO26_APPROVED_EVENT_SHA',''));(a.out/'work/trust.json').write_text(json.dumps({'passed':good,'approvedSHA':os.environ.get('DEVECO26_APPROVED_EVENT_SHA',''),'eventSHA':context.get('eventSHA'),'formalArtifactAllowed':False})+'\n');return 0 if good else 1
 if not json.loads((a.out/'public/ci-status.json').read_text()).get('stepsPassed'):return 1
 output('source',source);return 0
if __name__=='__main__':raise SystemExit(main())
