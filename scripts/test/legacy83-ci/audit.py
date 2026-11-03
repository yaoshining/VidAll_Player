#!/usr/bin/env python3
"""只接收本仓库 CI 当前提交的完整 HAR；记录实际工具链与旧核心边界。"""
import argparse,hashlib,json,os,re,shutil,subprocess,tarfile,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect_har(path,required,allowed):
 rows=[];seen=set()
 with tarfile.open(path) as archive:
  for member in archive.getmembers():
   name=member.name.removeprefix('package/')
   if name in seen:raise ValueError('HAR 成员重名')
   seen.add(name)
   if member.isfile() and name.startswith('libs/'):
    data=archive.extractfile(member).read();rows.append({'path':name,'bytes':len(data),'sha256':sha(data)})
 if {r['path'] for r in rows}!=allowed:raise ValueError('HAR 库集合变化')
 for row in rows:
  if row['path'] in required and row['sha256']!=required[row['path']]:raise ValueError('旧核心/运行库发生漂移')
 return {'harSHA256':sha(path.read_bytes()),'harBytes':path.stat().st_size,'libraries':sorted(rows,key=lambda r:r['path'])}
def ci_identity(env,commit):
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_SHA')!=commit or env.get('GITHUB_REPOSITORY')!='yaoshining/VidAll_Player' or not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('不是真实当前 CI 提交')
 if not all(re.fullmatch('[1-9][0-9]*',env.get(k,'')) for k in ['GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT']):raise ValueError('缺少 CI run 身份')
 return {'sourceCommit':commit,'repository':env['GITHUB_REPOSITORY'],'runId':env['GITHUB_RUN_ID'],'runAttempt':env['GITHUB_RUN_ATTEMPT'],'runURL':f"https://github.com/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"}
def command(args):return subprocess.check_output([str(a) for a in args],cwd=ROOT,text=True).strip()
def symbols(tool,path,defined=False):
 return sorted({l.split()[-1].split('@')[0] for l in command([tool,'-D','--defined-only' if defined else '--undefined-only',path]).splitlines() if l.split()})
def needed(tool,path):return sorted(re.findall(r'Shared library: \[([^\]]+)\]',command([tool,'-d',path])))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--studio',type=Path,required=True);args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
 commit=command(['git','rev-parse','HEAD']);result=ci_identity(os.environ,commit)
 command(['git','diff','--exit-code','HEAD','--'])
 lock=json.loads((HERE/'inputs.json').read_text());har=ROOT/'packages/vidall-player/build/default/outputs/default/vidall_player.har'
 result.update(inspect_har(har,lock['fixedLibraries'],set(lock['libraries'])))
 native=args.studio/'Contents/sdk/default/openharmony/native';llvm=native/'llvm/bin';abi={}
 with tempfile.TemporaryDirectory() as td,tarfile.open(har) as archive:
  extracted={}
  for m in archive.getmembers():
   name=m.name.removeprefix('package/')
   if name in lock['libraries']:
    path=Path(td)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.extractfile(m).read());extracted[name]=path
  for architecture in ['arm64-v8a','x86_64']:
   bridge=extracted[f'libs/{architecture}/libvidall_player_native.so'];runtime=extracted[f'libs/{architecture}/libc++_shared.so']
   imports=symbols(llvm/'llvm-nm',bridge);deps=needed(llvm/'llvm-readelf',bridge);baseline=lock['abi'][architecture]
   if imports!=baseline['imports'] or deps!=baseline['needed']:raise ValueError('桥接库依赖/导入集合变化：'+architecture)
   exports=set(symbols(llvm/'llvm-nm',runtime,True));cpp={s for s in imports if s.startswith(('_ZNSt','_ZNKSt','_ZT','__cxa','_Unwind','_Zdl','_Zda','_Znw','_Zna'))}
   missing=sorted(cpp-exports-{'__cxa_atexit','__cxa_finalize'})
   if missing:raise ValueError('固定运行库不满足 C++ 导入')
   abi[architecture]={'imports':imports,'needed':deps,'missingCxxImports':missing,'matchesOriginalHar':True}
  module=next(m for m in archive.getmembers() if m.name.endswith('src/main/module.json'));result['module']=json.loads(archive.extractfile(module).read())
 result['abi']=abi
 contents=args.studio/'Contents';studio=json.loads((contents/'Resources/product-info.json').read_text());sdk=json.loads((native/'oh-uni-package.json').read_text())
 result['toolchain']={'studioVersion':studio.get('version'),'nativeSdk':sdk,'node':command([contents/'tools/node/bin/node','--version']),'compiler':command([llvm/'clang','--version']),'cli':json.loads((HERE/'node_modules/@deveco/deveco-cli/package.json').read_text())['version'],'hashes':{str(p.relative_to(contents)):sha(p.read_bytes()) for p in [contents/'Resources/product-info.json',native/'oh-uni-package.json',llvm/'clang',llvm/'llvm-nm',llvm/'llvm-readelf']}}
 result['validation']={'devicePlayback':False,'ffmpegBuilt':False,'otherProjectTriggered':False,'artifactOrigin':'GitHub Actions 完整 Player 工程构建'}
 shutil.copyfile(har,out/'vidall_player-issue83-ci.har');(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(out/'SHA256SUMS').write_text(result['harSHA256']+'  vidall_player-issue83-ci.har\n')
 print(json.dumps({'sourceCommit':commit,'runURL':result['runURL'],'harSHA256':result['harSHA256'],'bytes':result['harBytes']},ensure_ascii=False))
if __name__=='__main__':main()
