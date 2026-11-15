"""从全局恢复验收页派生已停止Release挂起诊断；不改变生产HAR。"""
import argparse
from pathlib import Path

def transform(source):
 marker="    this.record('before-global-first-frame');"
 if source.count(marker)!=1 or 'release-probe.mp4' in source or 'global-probe.mp4' not in source:
  raise ValueError('释放探针插入位置漂移或已转换')
 source=source.replace('global-probe.mp4','release-probe.mp4').replace("scope: 'timer-global'", "scope: 'stopped-release-hold'")
 return source.replace(marker,marker+'''
    await this.delay(1500);
    this.record('release-probe-request');
    first.release().then((): void => { this.record('release-probe-returned'); },
      (error: Error): void => { this.record('release-probe-rejected', error.message); });''',1)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);a=p.parse_args()
 page=a.project/'entry/src/main/ets/pages/Index.ets';page.write_text(transform(page.read_text()))
 raw=a.project/'entry/src/main/resources/rawfile';(raw/'release-probe.mp4').write_bytes((raw/'global-probe.mp4').read_bytes())
