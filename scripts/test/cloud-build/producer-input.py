#!/usr/bin/env python3
"""消费现有004精确交付；未来核心变化须另有producer完整目标交付审查。"""
import argparse,hashlib,json,importlib.util
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('context010producer',HERE.parent/'normal-core/ci-context.py');CONTEXT=importlib.util.module_from_spec(spec);spec.loader.exec_module(CONTEXT)
def proof(r,source):
 return r.get('passed') is True and r.get('sourceBefore')==source==r.get('sourceAfter') and r.get('files')==load_lock()['files'] and r.get('producerLatestNormalFullCloudRebuildVerified') is False
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_lock():return json.loads((HERE/'producer-input-lock.json').read_text())
def verify(root,lock):
 base=root/'release/inputs/004-normal-core'
 if not lock.get('files'):raise ValueError('缺少精确producer基线')
 for rel,expected in lock['files'].items():
  parts=PurePosixPath(rel)
  if parts.is_absolute() or '..' in parts.parts:raise ValueError('producer输入路径越界')
  p=base
  for part in parts.parts:
   p=p/part
   if p.is_symlink():raise ValueError('producer输入符号链接拒绝')
  if not p.is_file() or sha(p)!=expected:raise ValueError('当前核心输入已变，必须提供经审查的producer新目标交付，不能借历史云端绿灯放行')
 return {'passed':True,'acceptedDelivery':'004-normal-core-phase30-a','futureCoreUpdates':'blocked-until-separate-producer-target-evidence-review','producerLatestNormalFullCloudRebuildVerified':False,'files':lock['files'],'formalArtifactAllowed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();work=a.out/'work';work.mkdir(parents=True,exist_ok=True)
 try:
  source=CONTEXT.snapshot(ROOT);r=verify(ROOT,load_lock());r.update(sourceBefore=source,sourceAfter=CONTEXT.assert_snapshot(ROOT,source))
 except Exception as e:r={'passed':False,'errorType':type(e).__name__,'error':str(e),'formalArtifactAllowed':False}
 (work/'producer-input-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':r['passed']}));raise SystemExit(0 if r['passed'] else 1)
