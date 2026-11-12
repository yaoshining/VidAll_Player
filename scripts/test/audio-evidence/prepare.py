#!/usr/bin/env python3
"""给现有关闭/全局诊断页面增加显式内录入口，保留原资格、Surface及流程。"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]


def with_capture(source):
    if "from './AudioCapture'" in source:
        raise ValueError('禁止重复插入录制器')
    changes = {
        'struct Index {': "struct Index {\n  @State audioRequested: boolean = false;\n  private capture?: AudioCapture;",
        'private maybeStart(): void {': 'private maybeStart(): void {\n    if (!this.audioRequested) return;',
        'private active(): void {': 'private active(): void {\n    this.capture?.assertRecording();',
        'private async run(): Promise<void> {': '''private async run(): Promise<void> {
    this.capture = new AudioCapture((event: string, value: string) => { this.record(event, value); });
    try {
      this.status = '请确认系统内录；录制开始后执行原故障验证';
      await this.capture.start(this.root + '/capture.mp4');
      this.active();
      await this.runUnrecorded();
      await this.delay(2500);
      this.capture.assertRecording();
    } finally { await this.capture.finish(); }
    this.record('capture-flow-completed', '仍需审阅实际音轨、PID、故障归属与硬件日志');
  }
  private async runUnrecorded(): Promise<void> {''',
        'aboutToDisappear(): void {': "aboutToDisappear(): void {\n    this.capture?.finish().catch((error: Error) => { this.record('capture-cleanup-failed', error.message); });",
        'Stack({ alignContent: Alignment.TopStart }) {': 'Stack({ alignContent: Alignment.TopStart }) {',
    }
    for before, after in changes.items():
        if source.count(before) != 1:
            raise ValueError('原探针源码变动，需重新审查接入位置：' + before)
        source = source.replace(before, after, 1)
    # 插在视频组件之后，避免被Surface或覆盖层挡住；保持原遥控器动作。
    marker = "    }.width('100%').height('100%').backgroundColor(Color.Black)"
    if source.count(marker) != 1:
        raise ValueError('探针根布局变动，不能猜测按钮位置')
    source = source.replace(marker, '''      if (!this.audioRequested) {
        Button('开始故障音频内录').id('fault-audio-start').defaultFocus(true).onClick(() => {
          this.audioRequested = true; this.maybeStart();
        })
      }
''' + marker)
    return "import { AudioCapture } from './AudioCapture';\n" + source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',choices=['recovery-fence','recovery-terminal'],required=True)
    parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args()
    target=args.project/'entry/src/main/ets/pages'
    if not target.is_dir():raise ValueError('必须指定已准备好完整HAR和签名配置的独立工程')
    fixture=ROOT/'fixtures/normal-core-consumer'/args.probe
    generated=with_capture((fixture/'Index.ets').read_text())
    for file in fixture.glob('*.ets'):
        if file.name!='Index.ets':shutil.copyfile(file,target/file.name)
    shutil.copyfile(ROOT/'fixtures/normal-core-consumer/recovery-terminal/ProbeChecks.ets',target/'ProbeChecks.ets')
    shutil.copyfile(ROOT/'fixtures/normal-core-consumer/audio-evidence/AudioCapture.ets',target/'AudioCapture.ets')
    (target/'Index.ets').write_text(generated)
    print('仅更新独立诊断页面；HAR和素材保持原样，模式配置需另行核对。')

if __name__=='__main__':main()
