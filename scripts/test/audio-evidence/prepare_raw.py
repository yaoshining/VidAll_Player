#!/usr/bin/env python3
"""在已签名配置的独立消费者中加入原始采集诊断；原HAR不变。"""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def prepare(project):
    har=project/'entry/libs/current.har';before=hashlib.sha256(har.read_bytes()).hexdigest()
    native=project/'entry/src/main/cpp';native.mkdir(parents=True,exist_ok=True)
    source=ROOT/'fixtures/normal-core-consumer/raw-capture'
    for name in ('bounded_capture.h','raw_capture.cpp','CMakeLists.txt'):shutil.copyfile(source/name,native/name)
    types=native/'types/libraw_capture';types.mkdir(parents=True,exist_ok=True)
    (types/'oh-package.json5').write_text(json.dumps({'name':'libraw_capture.so','version':'1.0.0','types':'./index.d.ts'}))
    (types/'index.d.ts').write_text('export const start: () => Promise<string>;\nexport const status: () => string;\nexport const finish: (fd: number) => Promise<string>;\n')
    profile=project/'entry/build-profile.json5';d=json.loads(profile.read_text());d.setdefault('buildOption',{})['externalNativeOptions']={'path':'./src/main/cpp/CMakeLists.txt','abiFilters':['arm64-v8a'],'arguments':'-DOHOS_STL=c++_static'};profile.write_text(json.dumps(d,indent=2))
    package=project/'entry/oh-package.json5';d=json.loads(package.read_text());d['dependencies'].pop('libpresentation_probe.so',None);d['dependencies']['libraw_capture.so']='file:./src/main/cpp/types/libraw_capture';package.write_text(json.dumps(d,indent=2))
    for name in ('Index.ets','RawCapture.ets'):shutil.copyfile(source/name,project/'entry/src/main/ets/pages'/name)
    shutil.copyfile(ROOT/'fixtures/normal-core-consumer/audio-evidence/TimeAnchor.ets',project/'entry/src/main/ets/pages/TimeAnchor.ets')
    assert hashlib.sha256(har.read_bytes()).hexdigest()==before
    return before
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);a=p.parse_args();print(prepare(a.project))
