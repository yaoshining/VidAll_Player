#!/usr/bin/env python3
"""只允许白名单 UTF-8 文本证据通过上传门禁。"""
import json,re,sys
from pathlib import Path

def verify(root):
 errors=[];count=0
 if not root.is_dir() or root.is_symlink():return ['证据目录缺失或是符号链接']
 for p in root.rglob('*'):
  name=str(p.relative_to(root))
  if p.is_symlink():errors.append('拒绝符号链接 '+name);continue
  if p.is_dir():continue
  count+=1
  if p.suffix not in {'.json','.log'}:errors.append('拒绝非白名单扩展 '+name);continue
  if p.stat().st_size>8*1024*1024:errors.append('文本超出大小限制 '+name);continue
  try:text=p.read_text(encoding='utf-8')
  except UnicodeError:errors.append('拒绝非 UTF-8 '+name);continue
  if '\0' in text:errors.append('拒绝二进制内容 '+name)
  if re.search(r'/(?:Users|private/tmp|Applications|home/runner|tmp)/',text):errors.append('未脱敏宿主路径 '+name)
  if p.suffix=='.json':
   try:json.loads(text)
   except ValueError:errors.append('无效 JSON '+name)
 if not count:errors.append('没有文本证据')
 return errors
if __name__=='__main__':
 errors=verify(Path(sys.argv[1]));print(json.dumps({'passed':not errors,'errors':errors},ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
