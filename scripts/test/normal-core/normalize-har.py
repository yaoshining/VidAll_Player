#!/usr/bin/env python3
"""只规范 HAR 的归档元数据，保留路径、类型、权限和所有文件内容；不解包到磁盘。"""
import argparse, copy, gzip, hashlib, json, posixpath, sys, tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath

def stream_digest(stream):
 value=hashlib.sha256()
 for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
 return value.hexdigest()

def digest(path):
 with path.open('rb') as f:return stream_digest(f)

def members(tar):
 seen=set();result=[]
 for item in tar.getmembers():
  name=item.name
  if not name or name.startswith('/') or '\\' in name or '\0' in name or '..' in PurePosixPath(name).parts or PureWindowsPath(name).drive:
   raise ValueError('危险成员路径')
  canonical=posixpath.normpath(name)
  if canonical in {'.','..'} or canonical in seen:raise ValueError('重复或无效成员路径')
  seen.add(canonical)
  if item.type not in {tarfile.REGTYPE,tarfile.AREGTYPE,tarfile.DIRTYPE} or item.sparse is not None:raise ValueError('拒绝链接与特殊成员')
  if item.isdir() and item.size:raise ValueError('目录成员携带非空内容')
  result.append(item)
 return result

def manifest(path):
 rows=[]
 with tarfile.open(path,'r:*') as tar:
  for item in members(tar):
   content=tar.extractfile(item) if item.isreg() else None
   value=stream_digest(content) if content else None
   if content:content.close()
   rows.append({'path':item.name,'type':'file' if item.isreg() else 'directory','mode':item.mode,'size':item.size,'sha256':value})
 return sorted(rows,key=lambda row:row['path'])

def normalize(source,target):
 before=manifest(source)
 created=False
 try:
  with tarfile.open(source,'r:*') as tar:
   ordered=sorted(members(tar),key=lambda item:item.name)
   with target.open('xb') as raw:
    created=True
    with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as gz,tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as output:
     for original in ordered:
      item=copy.copy(original);item.pax_headers=dict(original.pax_headers)
      item.uid=0;item.gid=0;item.uname='';item.gname='';item.mtime=0
      for key in ['uid','gid','uname','gname','mtime']:item.pax_headers.pop(key,None)
      # 其他 PAX 信息保留，并固定字段顺序。长路径由 tarfile 原样编码。
      item.pax_headers=dict(sorted(item.pax_headers.items()))
      data=tar.extractfile(original) if original.isreg() else None
      try:output.addfile(item,data)
      finally:
       if data:data.close()
  after=manifest(target)
  if before!=after:raise ValueError('规范化后路径、类型、权限或内容发生变化')
 except BaseException:
  if created:target.unlink(missing_ok=True)
  raise
 return {'passed':True,'sourceSHA256':digest(source),'normalizedSHA256':digest(target),'members':len(before),'files':sum(row['type']=='file' for row in before),'payloadPreserved':True}

def compare(left,right):
 a,b=manifest(left),manifest(right)
 by_a={r['path']:r for r in a};by_b={r['path']:r for r in b}
 changed=[name for name in sorted(set(by_a)|set(by_b)) if by_a.get(name)!=by_b.get(name)]
 sha_a,sha_b=digest(left),digest(right)
 return {'passed':not changed and sha_a==sha_b,'memberPayloadsEqual':not changed,'archiveBytesEqual':sha_a==sha_b,'leftSHA256':sha_a,'rightSHA256':sha_b,'leftMembers':len(a),'rightMembers':len(b),'changedMembers':changed,'members':a if not changed else None,'formalArtifactAllowed':False}

def main():
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
 normal=sub.add_parser('normalize');normal.add_argument('source',type=Path);normal.add_argument('target',type=Path)
 comparison=sub.add_parser('compare');comparison.add_argument('left',type=Path);comparison.add_argument('right',type=Path);comparison.add_argument('--report',type=Path,required=True)
 args=parser.parse_args()
 try:
  if args.command=='normalize':result=normalize(args.source,args.target)
  else:
   result=compare(args.left,args.right)
   with args.report.open('x') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1
 except (ValueError,OSError,tarfile.TarError,EOFError) as error:
  print('HAR 门禁拒绝：'+str(error),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
