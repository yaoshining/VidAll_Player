#!/usr/bin/env python3
"""编译真实 NativeSession 父级函数和 process_runtime；只替换平台API。"""
import argparse,hashlib,json,re,subprocess,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def extract(text,signature):
 start=text.index(signature);opening=text.index('{',start);depth=0;quote=None;escape=False;line_comment=False;block_comment=False;i=opening
 while i<len(text):
  ch=text[i];nx=text[i:i+2]
  if line_comment:
   if ch=='\n':line_comment=False
  elif block_comment:
   if nx=='*/':block_comment=False;i+=1
  elif quote:
   if escape:escape=False
   elif ch=='\\':escape=True
   elif ch==quote:quote=None
  elif nx=='//':line_comment=True;i+=1
  elif nx=='/*':block_comment=True;i+=1
  elif ch in '\"\'':quote=ch
  elif ch=='{':depth+=1
  elif ch=='}':
   depth-=1
   if depth==0:return text[start:i+1]
  i+=1
 raise ValueError(signature)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--mutate',choices=['destroy-guards','deadline-exit','deadline-missing','deadline-immediate']);ap.add_argument('--case',action='append');args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
 source=ROOT/'packages/vidall-player/src/main/cpp/napi_init.cpp';text=source.read_text();signatures=['NativeSession()','~NativeSession()','void Release()','void InvalidateCompletion()','void StopRendererLocked()','void DestroyRenderer()','void CloseCallbackLocked()','void DeleteSession(NativeSession* session)','void CleanupSessions(void*)'];parts={s:extract(text,s) for s in signatures}
 original_parts=dict(parts)
 if args.mutate=='destroy-guards':parts['void DestroyRenderer()']=parts['void DestroyRenderer()'].replace('vidall::runtime::ParkIfTerminal();','')
 shell=(Path(__file__).parent/'shell.cpp').read_text()
 for sig,code in parts.items():shell=shell.replace('/* EXTRACT '+sig+' */',code)
 (out/'actual.cpp').write_text(shell)
 binding={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'functions':{s:{'sha256':hashlib.sha256(c.encode()).hexdigest(),'text':c} for s,c in parts.items()},'harnessTemplateSHA256':hashlib.sha256((Path(__file__).parent/'shell.cpp').read_bytes()).hexdigest(),'runnerSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'compiledTranslationUnitSHA256':hashlib.sha256((out/'actual.cpp').read_bytes()).hexdigest(),'mutation':args.mutate,'originalFunctionSHA256':{s:hashlib.sha256(c.encode()).hexdigest() for s,c in original_parts.items()},'runtimeSHA256':hashlib.sha256((ROOT/'native/runtime/process_runtime.cpp').read_bytes()).hexdigest()};(out/'source-binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
 runtime=(ROOT/'native/runtime/process_runtime.cpp').read_text()
 if args.mutate=='deadline-exit':runtime=runtime.replace('std::_Exit(86)','std::_Exit(0)')
 if args.mutate=='deadline-missing':runtime=runtime.replace('std::_Exit(86)','(void)0')
 if args.mutate=='deadline-immediate':runtime=runtime.replace('first&&Now()-first>=deadline.load()','first')
 (out/'runtime.cpp').write_text(runtime)
 binding['compiledRuntimeSHA256']=hashlib.sha256((out/'runtime.cpp').read_bytes()).hexdigest();(out/'source-binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
 command=['clang++','-std=c++17','-pthread','-DVIDALL_MPV_AVAILABLE=1','-I'+str(ROOT/'native/runtime'),'-I'+str(ROOT/'release/inputs/004-normal-core/include'),str(out/'actual.cpp'),str(out/'runtime.cpp'),'-o',str(out/'test')]
 compiled=subprocess.run(command,text=True,capture_output=True);(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
 if compiled.returncode:print(compiled.stderr);return 2
 cases=['normal-last-reference','normal-explicit-release','terminal-before-last-reference','terminal-direct-destructor','terminal-render-tail','terminal-during-render-free','terminal-callback-close','terminal-cleanup-swap','terminal-callback-delivery-blocked','terminal-logger-blocked']
 if args.case:cases=args.case
 results=[]
 for case in cases:
  started=time.monotonic()
  proc=subprocess.Popen([str(out/'test'),case,str(out/case)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  lines=[];trigger_times=[]
  def receive():
   for line in proc.stdout:
    lines.append(line)
    if line.startswith('TERMINAL '):trigger_times.append(time.monotonic()*1000)
  reader=threading.Thread(target=receive);reader.start()
  try:rc=proc.wait(timeout=4)
  except subprocess.TimeoutExpired:rc='timeout';proc.kill();proc.wait()
  finished_ms=time.monotonic()*1000;reader.join();log=''.join(lines)
  (out/(case+'.log')).write_text(log)
  terminal=case.startswith('terminal-');forbidden=[line for line in log.splitlines() if line.startswith('DESTROY ') and 'after_terminal=1' in line]
  required=['DESTROY renderer','DESTROY egl-surface','DESTROY egl-context','DESTROY egl-display','DESTROY window','DESTROY callback','DESTROY mpv-player','EVENT event-thread-exit','EVENT render-thread-exit','EVENT owner-delete']
  passed=rc==(86 if terminal else 0) and 'FAIL' not in log and (not forbidden if terminal else all(s in log for s in required)) and ('EVENT terminal' in log if terminal else True)
  match=re.search(r'TERMINAL first_ms=(\d+) observed_ms=(\d+) deadline_ms=(\d+)',log)
  deadline_elapsed=round(finished_ms-trigger_times[0]+int(match[2])-int(match[1]),2) if match and trigger_times else None
  deadline_valid=(match is not None and deadline_elapsed is not None and int(match[3])-10<=deadline_elapsed<=int(match[3])+500) if terminal else None
  if terminal:passed=passed and deadline_valid
  if case=='terminal-callback-delivery-blocked':passed=passed and 'EVENT callback-wait-enter' in log and 'callback-wait-return' not in log
  if case=='terminal-logger-blocked':passed=passed and 'EVENT logger-write-enter' in log and 'logger-write-return' not in log
  results.append({'case':case,'exit':rc,'seconds':round(time.monotonic()-started,3),'forbiddenEvents':forbidden,'deadlineElapsedMs':deadline_elapsed,'deadlineValid':deadline_valid,'passed':passed})
 report={'passed':all(x['passed'] for x in results),'cases':results,'sourceBindingSHA256':hashlib.sha256((out/'source-binding.json').read_bytes()).hexdigest(),'limits':['平台API被替身覆盖，不是GPU真实故障注入','std::thread、shared_ptr/unique_ptr、真实父级函数和process_runtime均实际编译执行','Start/render线程主体是最小调度替身；未逐字编译完整RenderLoop','callback场景阻塞生产者通知交付线程；logger场景堵塞独立审计pipe写线程，不冒称真实平台logger挂死']};(out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
