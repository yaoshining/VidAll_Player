#!/usr/bin/env python3
"""在独立消费工程准备同步测量页；保留HAR和故障/焦点语义。"""
import argparse
import hashlib
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[3]
def transform(source):
 changes={
  'const first = await this.open(1); await this.delay(5000);':'const first = await this.open(1); await this.delay(90000);',
  'const target = 20000;':'const target = 120000;',
  'durationMs, true) - 30000':'durationMs, true) - 180000',
  "this.record('diagnostics', JSON.stringify({ position: snapshot.fields.positionMs, backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));":"this.record('diagnostics', JSON.stringify({ position: snapshot.fields.positionMs, backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));\n    await this.delay(10000);",
  'const second = await this.open(2); await this.delay(5000);':'const second = await this.open(2); await this.delay(10000);',
  '标准路径：坏片失败后播放、暂停恢复、seek、关闭重开':'同步测量：90秒播放、暂停恢复、seek、关闭重开；等待录制结束'
 }
 for before,after in changes.items():
  if source.count(before)!=1:raise ValueError('验收源码漂移，需审查：'+before)
  source=source.replace(before,after)
 return source

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);a=p.parse_args()
 har=a.project/'entry/libs/current.har';before=hashlib.sha256(har.read_bytes()).hexdigest()
 target=a.project/'entry/src/main/ets/pages';assert target.is_dir()
 for source in (ROOT/'fixtures/normal-core-consumer/audio-evidence').glob('*.ets'):shutil.copyfile(source,target/source.name)
 index=target/'Index.ets';index.write_text(transform(index.read_text()))
 capture=target/'AudioCapture.ets';s=capture.read_text();assert s.count('videoBitrate: 1500000')==1;capture.write_text(s.replace('videoBitrate: 1500000','videoBitrate: 400000'))
 assert hashlib.sha256(har.read_bytes()).hexdigest()==before
 print('同步页已准备；HAR不变，须另行放入180秒同步素材及完整构建。')
if __name__=='__main__':main()
