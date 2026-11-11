import { worker, MessageEvents, ErrorEvent } from '@kit.ArkTS';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { AudioOutputProbe } from './FenceAudioProbe';

@ComponentV2
export struct CleanupProbe {
  @Param mediaPath: string = '';
  @Event done: () => void = () => {};
  @Local evidence: string = '等待 Surface';
  @Local surfaceReady: boolean = false;
  @Local running: boolean = false;
  private surface: XComponentController = new XComponentController();
  private instance?: worker.ThreadWorker;
  private timer: number = -1;
  private beats: number = 0;
  private requested: number = 0;
  private exited: boolean = false;
  private report(text: string): void {
    this.evidence = (this.evidence + '\n' + text).split('\n').slice(-12).join('\n');
    hilog.info(0xD001, 'CleanupVerify', 'CLEANUP_VERIFY %{public}s', text);
  }
  private start(): void {
    if (this.running) { return; }
    this.running = true;
    this.instance = new worker.ThreadWorker('entry/ets/workers/CleanupWorker.ets');
    this.instance.onmessage = (event: MessageEvents): void => { this.report(event.data as string); };
    this.instance.onerror = (event: ErrorEvent): void => { this.report('FAIL worker=' + event.message); };
    this.instance.onexit = (code: number): void => {
      this.exited = true;
      this.report('exit code=' + code + ' elapsedMs=' + (Date.now() - this.requested) + ' beats=' + this.beats);
      this.instance = undefined;
    };
    this.instance.postMessage({ surface: this.surface.getXComponentSurfaceId(), uri: 'file://' + this.mediaPath });
    this.timer = setInterval(() => {
      this.beats++;
      if (this.requested > 0 && this.beats % 10 === 0) { this.report('UI alive exited=' + this.exited + ' beats=' + this.beats); }
    }, 100);
  }
  private async terminate(): Promise<void> {
    if (!this.instance || this.requested > 0) { return; }
    const peaks = await AudioOutputProbe.peaks();
    this.report('audio peaks=' + peaks.map((n: number) => n.toFixed(4)).join(','));
    this.requested = Date.now();
    this.report('terminate requested beats=' + this.beats);
    this.instance.terminate();
  }
  aboutToDisappear(): void {
    if (this.timer >= 0) { clearInterval(this.timer); }
    if (this.instance) { this.instance.terminate(); this.instance = undefined; }
  }
  build() {
    NavDestination() {
      Column({ space: 12 }) {
        Text('2ad7fdd · NAPI 环境清理').fontSize(22).fontColor(Color.White)
        XComponent({ id: 'cleanup-surface', type: XComponentType.SURFACE, controller: this.surface })
          .width('100%').height(220).onLoad(() => { this.surfaceReady = true; this.report('surface ready'); })
        Button('启动软件解码会话').enabled(this.surfaceReady && !this.running).onClick(() => this.start())
        Button('销毁 Worker 环境').enabled(this.running).onClick(() => this.terminate())
        Button('返回列表').onClick(() => this.done())
        Text(this.evidence).fontSize(12).fontColor(Color.White)
      }.padding(16).width('100%').height('100%').backgroundColor('#191919')
    }.hideTitleBar(true)
  }
}
