import { hilog } from '@kit.PerformanceAnalysisKit';
import { AudioOutputProbe } from './FenceAudioProbe';
import fs from '@ohos.file.fs';
import { common } from '@kit.AbilityKit';
import { PlayerPage, PlayerPageParam } from '../pages/player/index';
import { VideoPlayerController } from '../components/core/player/VideoPlayerController';
import { FileExplorerContext, PlaybackContextItem } from '../components/core/player/PlaybackContext';
import { PlaybackBackendService } from '../services/playback/PlaybackBackendService';
import { PlaybackBackendDecision, ServicePlayerBackend } from '../services/playback/PlaybackBackendTypes';
import { VideoData } from '../components/core/player/VideoData';
import { WindowLayout } from '../utils/WindowLayout';

export class OfflinePlaybackHarness { static command: (value: string) => void = () => {}; }
class OfflineBackend extends PlaybackBackendService {
  backend: ServicePlayerBackend = 'mpv';
  override async chooseBackend(data: VideoData): Promise<PlaybackBackendDecision> {
    const decision = await super.chooseBackend(data);
    decision.preferredBackend = this.backend;
    console.info('[Offline84] choose=' + this.backend);
    return decision;
  }
}

/** 两集自制样片与正式播放页对照；不是正式文件源入口验收。 */
@Entry
@ComponentV2
struct FenceProbe {
  @Provider('pageStack') pageStack: NavPathStack = new NavPathStack();
  @Local ready: boolean = false;
  @Local evidence: string = '正在准备设备内样片';
  private paths: string[] = [];
  private active: boolean = true;
  private measuring: boolean = false;
  private watchId: number = -1;
  private routing: OfflineBackend = new OfflineBackend();
  @Local controller: VideoPlayerController = new VideoPlayerController(this.routing);

  aboutToAppear(): void {
    this.prepare().catch(() => this.report('样片准备失败'));
    OfflinePlaybackHarness.command = (value: string): void => {
      if (value === 'audio-mpv' || value === 'audio-av') {
        this.measureAudio(value === 'audio-mpv' ? 'mpv' : 'avplayer').catch((error: Error) => this.report('audio error=' + error.message));
      } else if (value === 'boundary-exit' || value === 'boundary-switch') {
        this.testBoundary(value === 'boundary-exit').catch((error: Error) => this.report('boundary error=' + error.message));
      } else if (value === 'healthy-a' || value === 'healthy-b') {
        this.healthy(value === 'healthy-a' ? 0 : 1).catch((error: Error) => this.report(error.message));
      } else if (value === 'bad') { this.open(2, 'mpv', true);
      } else if (value === 'mpv') { this.open(1, 'mpv', true); }
      else if (value === 'resume') { this.open(1, 'mpv', false); }
      else if (value === 'avplayer') { this.open(1, 'avplayer', true); }
      else if (value === 'eof') { this.open(0, 'mpv', true); }
      else if (value === 'pause') { this.controller.pause().catch(() => this.report('pause failed')); }
      else if (value === 'play') {
        this.controller.allowPlaybackFromUser();
        this.controller.play().catch(() => this.report('play failed'));
      } else if (value === 'seek') {
        this.controller.allowPlaybackFromUser();
        this.controller.seek(45000).catch(() => this.report('seek failed'));
      } else if (value === 'back') { this.pageStack.pop(); }
      else if (value === 'status') { this.status(); }
    };
  }
  private report(value: string): void {
    this.evidence = (this.evidence + '\n' + value).split('\n').slice(-16).join('\n');
    console.info('[Offline84] ' + value);
    if (value.startsWith('audio phase=') || value.startsWith('hw=') || value.startsWith('backend=') || value.includes('error=')) {
      hilog.info(0xD001, 'FenceVerify', 'FENCE_VERIFY %{public}s', value);
    }
  }
  private status(): void {
    this.report(`backend=${this.controller.backend} ready=${this.controller.isReady} playing=${this.controller.isPlaying} position=${this.controller.currentTime} duration=${this.controller.duration} index=${this.controller.playbackContext?.currentIndex ?? -1} failure=${this.controller.playbackFailure.length > 0}`);
  }
  private async healthy(index: number): Promise<void> {
    if (!this.ready || this.measuring) { return; }
    this.measuring = true;
    AppStorage.setOrCreate('fenceHardware', '等待视频参数');
    try {
      hilog.info(0xD001, 'FenceVerify', 'FENCE_VERIFY open index=%{public}d', index);
      this.open(index, 'mpv', true);
      for (let n = 0; n < 150 && !this.controller.isPlaying && !this.controller.playbackFailure; n++) {
        await AudioOutputProbe.delay(100);
      }
      this.report('健康片 ' + (this.controller.playbackFailure || '已打开'));
      for (let n = 0; n < 3; n++) {
        await this.measurePhase('clip-' + index + '/' + n);
        this.report(AppStorage.get<string>('fenceHardware') ?? '等待视频参数');
      }
    } catch (err) { this.report(String(err)); }
    finally {
      this.measuring = false;
      if (this.pageStack.size() > 0) { this.pageStack.pop(); }
      setTimeout(() => {
        const active = this.active && this.pageStack.size() === 0;
        this.report('关闭 7 秒后列表可用=' + active + ' 片号=' + index);
        hilog.info(0xD001, 'FenceVerify', 'FENCE_VERIFY list active=%{public}s index=%{public}d', String(active), index);
      }, 7000);
    }
  }
  private async measureAudio(backend: ServicePlayerBackend): Promise<void> {
    if (!this.ready || this.measuring || this.pageStack.size() > 0) { return; }
    this.measuring = true;
    try {
      this.report(AudioOutputProbe.capabilities());
      await AudioOutputProbe.delay(800);
      await this.measurePhase('idle');
      this.open(1, backend, true);
      // 与生产页的 45 秒准备上限对齐，也留出 Surface 切换的收尾时间。
      for (let n = 0; n < 250 && !this.controller.isPlaying && !this.controller.playbackFailure; n++) {
        await AudioOutputProbe.delay(200);
      }
      if (!this.controller.isPlaying) { throw new Error('playback did not start'); }
      await this.measurePhase('playing');
      await this.controller.pause();
      await AudioOutputProbe.delay(800);
      await this.measurePhase('paused');
      this.controller.allowPlaybackFromUser();
      await this.controller.play();
      await AudioOutputProbe.delay(800);
      await this.measurePhase('user-resume');
      const alarm = await AudioOutputProbe.alarm();
      try {
        await AudioOutputProbe.delay(800);
        await this.measurePhase('system-alarm');
      } finally {
        try { await alarm.stop(); } finally { await alarm.release(); }
      }
      await AudioOutputProbe.delay(900);
      await this.measurePhase('alarm-ended');
      if (this.controller.isPlaying && backend === 'mpv') {
        await this.controller.pause();
        await AudioOutputProbe.delay(600);
        await this.measurePhase('manual-pause-after-alarm');
      }
      this.controller.allowPlaybackFromUser();
      await this.controller.play();
      await AudioOutputProbe.delay(800);
      await this.measurePhase('final-resume');
    } finally {
      this.measuring = false;
      if (this.pageStack.size() > 0) { this.pageStack.pop(); }
    }
  }
  private async testBoundary(exit: boolean): Promise<void> {
    if (this.measuring) { return; }
    this.measuring = true;
    try {
      this.open(exit ? 1 : 0, 'mpv', true);
      for (let i = 0; i < 150 && !this.controller.isPlaying; i++) { await AudioOutputProbe.delay(100); }
      await this.measurePhase('boundary-playing');
      await this.controller.pause();
      await AudioOutputProbe.delay(800);
      this.controller.allowPlaybackFromUser();
      await this.controller.play();
      await AudioOutputProbe.delay(800);
      await this.measurePhase('boundary-user-resume');
      const alarm = await AudioOutputProbe.alarm();
      try {
        await AudioOutputProbe.delay(800);
        await this.measurePhase('boundary-interrupted');
        if (this.controller.isPlaying) { throw new Error('未实际打断'); }
        if (exit) {
          this.pageStack.pop();
          await AudioOutputProbe.delay(1000);
        }
      } finally {
        try { await alarm.stop(); } finally { await alarm.release(); }
      }
      if (exit) {
        this.open(0, 'mpv', true);
      } else {
        this.report('awaiting-next-episode');
      }
      for (let i = 0; i < 150; i++) {
        if (this.controller.playbackContext?.currentIndex === (exit ? 0 : 1) && this.controller.isPlaying) { break; }
        await AudioOutputProbe.delay(150);
      }
      this.status();
      await this.measurePhase(exit ? 'after-exit' : 'after-switch');
    } finally {
      this.measuring = false;
      if (this.pageStack.size() > 0) { this.pageStack.pop(); }
    }
  }
  private async measurePhase(name: string): Promise<void> {
    const position = this.controller.currentTime;
    const peaks = await AudioOutputProbe.peaks();
    this.report('audio phase=' + name + ' backend=' + this.controller.backend + ' playing=' +
      this.controller.isPlaying + ' from=' + position + ' to=' + this.controller.currentTime +
      ' peaks=' + peaks.map((n: number) => n.toFixed(4)).join(','));
  }
  private async prepare(): Promise<void> {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;

    for (const name of ['issue84-ep01.mp4', 'issue84-ep02.mp4', 'broken.mp4']) {
      const bytes = await context.resourceManager.getRawFileContent(name);
      if (!this.active) { return; }
      const path = context.cacheDir + '/' + name;
      const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      try { fs.writeSync(file.fd, bytes.buffer); } finally { fs.closeSync(file); }
      this.paths.push(path);
      this.report(`${name} bytes=${bytes.byteLength}`);
    }
    this.ready = true;
  }
  private open(index: number, backend: ServicePlayerBackend, restart: boolean): void {
    if (!this.ready || this.pageStack.size() > 0) { return; }
    this.routing.backend = backend;
    this.controller = new VideoPlayerController(this.routing);
    const context = new FileExplorerContext();
    context.items = this.paths.map((path: string, i: number): PlaybackContextItem => ({
      videoPath: 'file://' + path, title: i === 2 ? '损坏 MP4' : '正常 MP4', index: i
    }));
    context.currentIndex = index;
    const param: PlayerPageParam = {
      url: backend === 'mpv' ? 'file://' + this.paths[index] : undefined,
      fileUrl: backend === 'avplayer' ? this.paths[index] : undefined,
      title: context.items[index].title, durationHintMs: index === 0 ? 22000 : 120000,
      preferredBackend: backend, mediaKey: 'media_progress_offline84_' + index,
      restartFromBeginning: restart, playbackContext: context
    };
    this.report(`open index=${index} requested=${backend} restart=${restart}`);
    this.pageStack.pushPath({ name: PlayerPage.PAGE_NAME, param });
    if (this.watchId >= 0) { clearInterval(this.watchId); }
    this.watchId = setInterval(() => {
      if (this.controller.playbackFailure) this.report('播放失败 ' + this.controller.playbackFailure);
      if (this.pageStack.size() === 0) { clearInterval(this.watchId); this.watchId = -1; }
    }, 1000);
  }
  aboutToDisappear(): void {
    this.active = false;
    if (this.watchId >= 0) { clearInterval(this.watchId); }
    OfflinePlaybackHarness.command = () => {};
    for (const path of this.paths) { try { fs.unlinkSync(path); } catch (_) {} }
  }
  @Builder destination(name: string) {
    if (name === PlayerPage.PAGE_NAME) { PlayerPage({ videoPlayerController: this.controller }) }
  }
  build() {
    Navigation(this.pageStack) {
      Scroll() {
        Column({ space: 16 }) {
          Text('联合关闭恢复 · d287e45').fontSize(28).fontColor(Color.White)
          Text('损坏文件报错后使用播放页的返回按钮，再选正常文件。').fontColor(Color.White)
          Button('损坏 MP4').enabled(this.ready).onClick(() => this.open(2, 'mpv', true))
          Button('A · 播放并关闭').enabled(this.ready).onClick(() => this.healthy(0))
          Button('B · 播放另一部并测音画').enabled(this.ready).onClick(() => this.healthy(1))
          Button('音频中断与单次恢复').enabled(this.ready).onClick(() => OfflinePlaybackHarness.command('audio-mpv'))
          Button('中断后退出并重播').enabled(this.ready).onClick(() => OfflinePlaybackHarness.command('boundary-exit'))
          Button('中断后换集').enabled(this.ready).onClick(() => OfflinePlaybackHarness.command('boundary-switch'))
          Text(this.evidence).fontSize(14).fontColor('#DDDDDD')
        }.width('100%').padding(20)
      }.width('100%').height('100%')
    }.hideTitleBar(true).mode(NavigationMode.Stack).navDestination(this.destination)
      .width('100%').height('100%').backgroundColor('#191919')
      .onAreaChange((_, area) => { WindowLayout.getInstance().update(Number(area.width), Number(area.height)); })
  }
}
