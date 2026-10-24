#!/usr/bin/env python3
"""保留原test-player完整native/诊断覆盖；云端无签名、无设备。"""
import argparse,importlib.util,json,os,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
s=importlib.util.spec_from_file_location('eval010host',HERE.parent/'deveco26/evaluate.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E)
command=E.TARGET.command
EXPECTED={'ohcodec_runtime_test','session_lifecycle_test','localhost_proxy_lease_test','player_session_test','surface_renderer_test','event_dispatcher_test','media_loader_test','tracks_subtitles_test','subtitle_rendering_test','adaptive_streaming_test','capability_report_test','media_parameters_test','render_backend_policy_test','diagnostics_test'}
def test_inventory(data):
 names=[x['name'] for x in data['tests']]
 if set(names)!=EXPECTED or len(names)!=len(EXPECTED):raise ValueError('CTest独有检查集合缺失/重复/扩大')
 return True
def proof(r,source):
 return r.get('passed') is True and r.get('sourceBefore')==source==r.get('sourceAfter') and r.get('ctestNames')==sorted(EXPECTED) and r.get('ctestPassed')==14 and r.get('diagnosticsJS')==['diagnostics-session','diagnostics-device']
def execute(root,out):
 work=out/'work';work.mkdir(parents=True,exist_ok=True);build=out/'legacy-native-build';rows=[];result={'passed':False,'commands':rows,'formalArtifactAllowed':False};child={**os.environ,'TYPESCRIPT_PATH':str(root/'scripts/test/normal-core/node_modules/typescript')}
 try:
  if build.exists():raise ValueError('拒绝复用旧native构建目录')
  source=E.CONTEXT.snapshot(root);result['sourceBefore']=source
  command('legacy-native-configure',['cmake','-S',root/'native/tests','-B',build],root,child,work,rows,120)
  command('legacy-native-build',['cmake','--build',build,'--parallel','4'],root,child,work,rows,300)
  inventory=json.loads(command('legacy-native-inventory',['ctest','--test-dir',build,'--show-only=json-v1'],root,child,work,rows,30));test_inventory(inventory)
  text=command('legacy-native-ctest',['ctest','--test-dir',build,'--output-on-failure'],root,child,work,rows,180)
  if not re.search(r'100% tests passed, 0 tests failed out of 14',text):raise ValueError('缺少14项真实CTest全部成功结论')
  for name in ['diagnostics-session','diagnostics-device']:command('legacy-'+name,['node',root/('native/tests/'+name+'.test.cjs')],root,child,work,rows,90)
  result.update(passed=True,sourceAfter=E.CONTEXT.assert_snapshot(root,source),ctestNames=sorted(EXPECTED),ctestPassed=14,diagnosticsJS=['diagnostics-session','diagnostics-device'])
 except Exception as error:result.update(errorType=type(error).__name__,error=E.redact(str(error)))
 (work/'legacy-native-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=execute(ROOT,a.out);print(json.dumps({'passed':r['passed']}));raise SystemExit(0 if r['passed'] else 1)
