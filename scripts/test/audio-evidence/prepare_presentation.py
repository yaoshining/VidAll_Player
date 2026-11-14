#!/usr/bin/env python3
"""仅在独立验收工程增加呈现能力查询库；不改原HAR及其九库。"""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def prepare(project):
 har=project/'entry/libs/current.har';before=hashlib.sha256(har.read_bytes()).hexdigest()
 native=project/'entry/src/main/cpp';native.mkdir(parents=True,exist_ok=True)
 for name in ['bounded_enumeration.h','presentation_probe.cpp','CMakeLists.txt']:
  shutil.copyfile(ROOT/'fixtures/normal-core-consumer/presentation-evidence'/name,native/name)
 types=native/'types/libpresentation_probe';types.mkdir(parents=True,exist_ok=True)
 (types/'oh-package.json5').write_text(json.dumps({'name':'libpresentation_probe.so','version':'1.0.0','types':'./index.d.ts'}))
 (types/'index.d.ts').write_text('export const query: () => Promise<string>;\n')
 profile=project/'entry/build-profile.json5';data=json.loads(profile.read_text());data.setdefault('buildOption',{})['externalNativeOptions']={'path':'./src/main/cpp/CMakeLists.txt','abiFilters':['arm64-v8a'],'arguments':'-DOHOS_STL=c++_static'};profile.write_text(json.dumps(data,indent=2))
 package=project/'entry/oh-package.json5';data=json.loads(package.read_text());data['dependencies']['libpresentation_probe.so']='file:./src/main/cpp/types/libpresentation_probe';package.write_text(json.dumps(data,indent=2))
 index=project/'entry/src/main/ets/pages/Index.ets';text=index.read_text()
 marker='    await initializePlayerRuntime(this.context, '
 if 'presentationProbe' in text or text.count(marker)!=1:raise ValueError('诊断页位置变化或已接入')
 text="import presentationProbe from 'libpresentation_probe.so';\n"+text
 text=text.replace(marker,"    const presentationCapabilities = await presentationProbe.query();\n    this.active();\n    this.record('presentation-capabilities', presentationCapabilities);\n"+marker,1)
 index.write_text(text)
 assert hashlib.sha256(har.read_bytes()).hexdigest()==before
 return before
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);a=p.parse_args();print(prepare(a.project))
