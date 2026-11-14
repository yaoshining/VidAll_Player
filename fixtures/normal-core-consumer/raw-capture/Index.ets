import { TimeAnchor } from './TimeAnchor';
import { RawCapture } from './RawCapture';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { window } from '@kit.ArkUI';
import { systemDateTime } from '@kit.BasicServicesKit';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, PlayerEvent } from '@vidall/player';

@Entry
@Component
struct Index {
  @State status: string = '准备原始音画采集';
  private context?: common.UIAbilityContext;
  private root: string = '';
  private ready: boolean = false;
  private surface: boolean = false;
  private running: boolean = false;
  private cancelled: boolean = false;
  private firstFrames: number = 0;
  private errors: number = 0;
  private controller: XComponentController = new XComponentController();
  private player?: VidAllPlayer;
  private capture?: RawCapture;
  private anchor?: TimeAnchor;
  private async delay(ms: number): Promise<void> {
    await new Promise<void>((resolve) => { setTimeout(resolve, ms); });
    if (this.cancelled) throw new Error('RAW_PAGE_CLOSED');
  }
  private record(event: string, value: string = ''): void {
    if (!this.root) return;
    const f = fs.openSync(this.root + '/events.jsonl', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.APPEND);
    try { fs.writeSync(f.fd, JSON.stringify({ event, value, time: Date.now(),
      monoNs: systemDateTime.getUptime(systemDateTime.TimeType.ACTIVE, true) }) + '\n'); } finally { fs.closeSync(f); }
  }
  aboutToAppear(): void { this.prepare().catch((e: Error) => { this.status = e.message; }); }
  aboutToDisappear(): void { this.cancelled = true; }
  private async prepare(): Promise<void> {
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.root = this.context.filesDir + '/phase17-raw';
    if (!fs.accessSync(this.root)) await fs.mkdir(this.root);
    const data = await this.context.resourceManager.getRawFileContent('test_video.mp4');
    const file = fs.openSync(this.root + '/test_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try { fs.writeSync(file.fd, data.buffer); } finally { fs.closeSync(file); }
    await initializePlayerRuntime(this.context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 });
    this.ready = true; this.status = '准备就绪：原始采集30秒，不录麦克风';
  }
  private async run(): Promise<void> {
    if (!this.ready || !this.surface || this.running || this.cancelled || !this.context) return;
    this.running = true;
    const w = await window.getLastWindow(this.context);
    this.capture = new RawCapture((e: string, v: string): void => { this.record(e, v); },
      async (ms: number): Promise<void> => { await new Promise<void>((resolve) => { setTimeout(resolve, ms); }); });
    try {
      await w.setWindowKeepScreenOn(true);
      this.status = '请允许本次录屏；只采测试画面及内录声音';
      await this.capture.start(this.root + '/capture.bin');
      this.anchor = new TimeAnchor((e: string, v: string): void => { this.record(e, v); },
        (_bits: number[]): void => {}, (ms: number): Promise<void> => this.delay(ms));
      await this.anchor.calibrate('before');
      await this.delay(1000); this.capture.assertRecording();
      const player = createPlayer({ playbackMode: 'standard', eventListener: (e: PlayerEvent): void => {
        if (e.type === 'firstFrame') this.firstFrames++;
        if (e.type === 'error') this.errors++;
        this.record('player-' + e.type, JSON.stringify(e));
      }});
      this.player = player;
      await player.attachSurface({ componentId: this.controller.getXComponentSurfaceId(), generation: 1, width: 1280, height: 720 });
      this.record('play-request');
      await player.load({ kind: 'localFile', uri: 'file://' + this.root + '/test_video.mp4' });
      await player.play();
      for (let i = 0; i < 100 && this.firstFrames === 0; i++) await this.delay(100);
      if (!this.firstFrames) throw new Error('RAW_NO_FRAME');
      this.record('open-diagnostics', JSON.stringify(await player.getDiagnostics()));
      this.status = '原始采集进行中，请等待30秒'; this.record('measure-start');
      for (let i = 0; i < 30; i++) { await this.delay(1000); this.capture.assertRecording(); if (this.errors) throw new Error('RAW_PLAYBACK_ERROR'); }
      this.record('measure-end');
      await player.release(); this.player = undefined; this.record('release-ok');
      await this.delay(2000);this.capture.assertRecording();
      await this.anchor.calibrate('after'); await this.anchor.close();
      await this.capture.finish();this.status = '原始采集完成，待导出分析';
    } catch (error) { this.status = '失败：' + (error as Error).message;this.record('failed', (error as Error).message); }
    finally {
      try { await this.player?.release();this.player = undefined; } catch(e) {this.record('release-failed',(e as Error).message);}
      try { await this.anchor?.close(); } catch(e) {this.record('anchor-close-failed',(e as Error).message);}
      try { await this.capture.finish(); } catch(e) {this.record('capture-failed',(e as Error).message);}
      await w.setWindowKeepScreenOn(false);
    }
  }
  build() {
    Stack() {
      XComponent({ id: 'raw-player', type: XComponentType.SURFACE, controller: this.controller })
        .width('100%').height('100%').onLoad(() => { this.surface = true; })
      Column() {
        Button('开始独立原始音画采集').id('raw-start').defaultFocus(true).onClick(() => { this.run().catch((e: Error) => { this.status = e.message; }); })
        Text(this.status).fontColor(Color.White).fontSize(20)
      }.position({ x: 0, y: 0 })
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
