#!/usr/bin/env python3
"""在已准备的独立验收页增加时间锚点；HAR、九库和故障门槛保持不变。"""
import argparse,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BEGIN='''
      this.anchor = new TimeAnchor((event: string, value: string): void => { this.record(event, value); },
        (bits: number[]): void => { this.anchorBits = bits; }, (ms: number): Promise<void> => this.delay(ms));
      this.anchor.startVisual();
      await this.anchor.calibrate('before');'''
END="      await this.anchor.calibrate('after');\n      await this.anchor.close();\n"
ROW='''      Row() {
        ForEach(this.anchorBits, (bit: number, index: number) => {
          Blank().width('6.25%').height(40).backgroundColor(bit === 1 ? Color.White : Color.Black)
        }, (bit: number, index: number): string => String(index) + '-' + String(bit))
      }.id('anchor-visual-row').width('100%').height(40).position({ x: 0, y: '90%' })
'''
def replace(source,before,after):
 if source.count(before)!=1:raise ValueError('锚点插入位置漂移：'+before)
 return source.replace(before,after,1)
def transform(source,kind):
 if "from './TimeAnchor'" in source:raise ValueError('禁止重复增加锚点')
 source=replace(source,'struct Index {','struct Index {\n  @State anchorBits: number[] = anchorCode(0);\n  private anchor?: TimeAnchor;')
 marker="await this.capture.start(this.root + '/capture.mp4');"
 source=replace(source,marker,marker+BEGIN)
 if kind=='normal':
  source=replace(source,'      await this.capture.finish();',END+'      await this.capture.finish();')
  # 无论失败/离页，锚点清理与原播放器清理分别处理；失败仍保留。
  source=replace(source,"  aboutToDisappear(): void {", "  aboutToDisappear(): void { this.anchor?.close().catch((error: Error) => { this.record('anchor-close-failed', error.message); });")
  marker='      try { await this.finish(); } catch (_) {}'
  source=replace(source,marker,"      try { await this.anchor?.close(); } catch (cleanup) { this.record('anchor-close-failed', (cleanup as Error).message); }\n"+marker)
 elif kind in ('fence','global'):
  source=replace(source,'      this.capture.assertRecording();\n    } finally { await this.capture.finish(); }',END+"      this.capture.assertRecording();\n    } finally { try { await this.anchor?.close(); } finally { await this.capture.finish(); } }")
  if kind=='fence':source=replace(source,'await this.delay(1500); this.active();','await this.delay(10000); this.active();')
  else:
   source=replace(source,'const second = await this.open(2); await this.delay(700);','const second = await this.open(2); await this.delay(10000);')
   source=replace(source,'const third = await this.open(3); await this.delay(2000);','const third = await this.open(3); await this.delay(10000);')
  source=replace(source,'  aboutToDisappear(): void {',"  aboutToDisappear(): void {\n    this.anchor?.close().catch((error: Error) => { this.record('anchor-close-failed', error.message); });")
 else:raise ValueError('未知验收页')
 source=replace(source,"    }.width('100%').height('100%').backgroundColor(Color.Black)",ROW+"    }.width('100%').height('100%').backgroundColor(Color.Black)")
 return "import { TimeAnchor, anchorCode } from './TimeAnchor';\n"+source

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--kind',choices=['normal','fence','global'],required=True);a=p.parse_args()
 har=a.project/'entry/libs/current.har';before=hashlib.sha256(har.read_bytes()).hexdigest();pages=a.project/'entry/src/main/ets/pages';index=pages/'Index.ets'
 index.write_text(transform(index.read_text(),a.kind));shutil.copyfile(ROOT/'fixtures/normal-core-consumer/audio-evidence/TimeAnchor.ets',pages/'TimeAnchor.ets')
 capture=pages/'AudioCapture.ets';text=capture.read_text()
 if text.count('videoBitrate: 1500000')==1:text=text.replace('videoBitrate: 1500000','videoBitrate: 400000')
 elif text.count('videoBitrate: 400000')!=1:raise ValueError('录制码率漂移')
 capture.write_text(text)
 assert hashlib.sha256(har.read_bytes()).hexdigest()==before
 print('独立锚点已加入诊断页，原HAR不变。')
if __name__=='__main__':main()
