#!/usr/bin/env python3
"""核验一套已保存的正例和变异反例，不将反例失败改成产品通过。"""
import json,sys,hashlib
from pathlib import Path
root=Path(sys.argv[1]);checks={}
def load(name):return json.loads((root/name/'results.json').read_text())
green=load('green-final');checks['green10']=green['passed'] and len(green['cases'])==10 and all(r['passed'] for r in green['cases'])
checks['terminal_time']=all(r['exit']==86 and r['deadlineValid'] and not r['forbiddenEvents'] for r in green['cases'] if r['case'].startswith('terminal-'))
guards=load('mutant-guards-final');checks['guard_mutant_rejected']=not guards['passed'] and len(guards['cases'])==2 and all(not r['passed'] and r['forbiddenEvents'] for r in guards['cases'])
early=load('mutant-immediate-final');checks['early_86_rejected']=not early['passed'] and len(early['cases'])==2 and all(r['exit']==86 and not r['deadlineValid'] and not r['passed'] for r in early['cases'])
missing=load('mutant-missing-final');checks['missing_deadline_rejected']=not missing['passed'] and len(missing['cases'])==2 and all(r['exit']=='timeout' and not r['passed'] for r in missing['cases'])
for name in ['green-final','mutant-guards-final','mutant-immediate-final','mutant-missing-final']:
 data=load(name);binding=root/name/'source-binding.json';checks[name+'_binding']=hashlib.sha256(binding.read_bytes()).hexdigest()==data['sourceBindingSHA256']
result={'passed':all(checks.values()),'checks':checks,'limits':green['limits']};print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(not result['passed'])
