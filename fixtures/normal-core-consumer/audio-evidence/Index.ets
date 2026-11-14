import { EvidenceChunks } from './EvidenceChunks';
import { SystemBaseline } from './SystemBaseline';
import { SeekSample, verifySeekProgress } from './SeekRun';
import { FocusAlarm } from './FocusAlarm';
import { FocusPort, FocusSnapshot, runFocusProbe } from './FocusRun';
import { AudioCapture } from './AudioCapture';
import { EvidenceFiles } from './EvidenceFiles';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { window } from '@kit.ArkUI';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, onPlayerTerminal, getPlayerRuntimeStatus, PlayerEvent, DiagnosticField, PlayerDiagnosticsSnapshot, PlayerLoadIdentity } from '@vidall/player';


@Entry
@Component
struct Index {
  @State evidenceStatus: string = '';
  @State captureBusy: boolean = false;
  private evidence?: EvidenceFiles;
  private chunks?: EvidenceChunks;
  @State captureTrace: string = '';
  private captureTraceLines: string[] = [];
  @State awaitingManualResume: boolean = false;
  @State status: string = '准备独立 HAR 验证';
  private controller: XComponentController = new XComponentController();
  private player?: VidAllPlayer;
  private ready: boolean = false;
  private surface: boolean = false;
  private started: boolean = false;
  private capture?: AudioCapture;
  private alarm?: FocusAlarm;
  private baseline?: SystemBaseline;
  private cancelled: boolean = false;
  private focusRequested: boolean = false;
  private manualResume: boolean = false;
  private firstFrames: number = 0;
  private playerState: string = 'idle';
  private errors: number = 0;
  private root: string = '';
  private context?: common.UIAbilityContext;
  private unsubscribe?: () => void;
  private async delay(ms: number): Promise<void> {
    await new Promise<void>((resolve) => { setTimeout(resolve, ms); }); this.active();
  }
  private active(): void {
    if (this.cancelled) throw new Error('PROBE_CANCELLED');
  }
  private record(event: string, value: string = ''): void {
    if (event === 'capture-stage') this.captureBusy = true;
    if (event === 'capture-closed') this.captureBusy = false;
    if (event.startsWith('capture-')) {
      const line = (event + ': ' + value).replace(/[\r\n]/g, ' ').slice(0, 160);
      this.captureTraceLines.push(line);
      if (this.captureTraceLines.length > 12) this.captureTraceLines.shift();
      this.captureTrace = this.captureTraceLines.join('\n');
    }
    console.info('P17 ' + event + ' ' + value);
    if (!this.root) return;
    const file = fs.openSync(this.root + '/events.jsonl', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.APPEND);
    fs.writeSync(file.fd, JSON.stringify({ time: Date.now(), event, value }) + '\n'); fs.closeSync(file);
  }
  private event(event: PlayerEvent): void {
    if (event.type === 'firstFrame') { this.firstFrames++; this.record('firstFrame', String(event.surfaceGeneration)); }
    if (event.type === 'error') { this.errors++; this.record('error', event.error?.code ?? 'unknown'); }
    if (event.type === 'state') { this.playerState = event.state ?? 'unknown'; this.record('state', this.playerState); }
  }
  aboutToAppear(): void { this.prepare().catch((error: Error) => { this.status = '准备失败'; this.record('prepare-failed', error.message); }); }
  private async prepare(): Promise<void> {
    this.active();
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.root = this.context.filesDir + '/phase17-audio';
    if (!fs.accessSync(this.root)) await fs.mkdir(this.root);
    this.evidence = new EvidenceFiles(this.context, this.root, (message: string): void => { this.evidenceStatus = message; });
    this.evidence.start();
    const data = await this.context.resourceManager.getRawFileContent('test_video.mp4');
    const file = await fs.open(this.root + '/test_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try { await fs.write(file.fd, data.buffer); } finally { await fs.close(file); }
    this.active();
    await initializePlayerRuntime(this.context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 });
    this.active();
    this.record('runtime', getPlayerRuntimeStatus().state);
    this.unsubscribe = onPlayerTerminal(() => { this.fatal().catch(() => { this.record('fatal-ui-error'); }); });
    this.ready = true; this.status = '准备就绪，请开始系统内录回归';
  }
  private async startCaptured(withFocus: boolean = false, systemBaseline: boolean = false): Promise<void> {
    if (this.cancelled || !this.ready || !this.surface || this.started) return;
    this.started = true; this.focusRequested = withFocus;
    this.capture = new AudioCapture((event: string, value: string) => { this.record(event, value); });
    try {
      this.status = '请在系统弹窗确认录制（不录麦克风）';
      await this.capture.start(this.root + '/capture.mp4');
      this.active(); this.capture.assertRecording();
      if (systemBaseline) {
        this.baseline = new SystemBaseline((event: string, value: string): void => { this.record(event, value); },
          (ms: number): Promise<void> => this.delay(ms));
        await this.baseline.run(this.root + '/test_video.mp4', this.controller.getXComponentSurfaceId());
        await this.delay(2500);
      } else { await this.run(); }
      this.capture.assertRecording();
      await this.capture.finish();
      this.status = '内录完成，待导出音轨核验；不等于听声通过';
    } catch (error) {
      this.status = '验收失败：' + (error as Error).message;
      this.record('failed', (error as Error).message);
      try { await this.finish(); } catch (_) {}
      try { await this.capture.finish(); } catch (_) {}
    }
  }
  private async firstFrameAfter(previous: number): Promise<void> {
    for (let i = 0; i < 100 && this.firstFrames <= previous; i++) await this.delay(100);
    if (this.firstFrames <= previous) throw new Error('FIRST_FRAME_TIMEOUT');
  }
  private async open(generation: number): Promise<VidAllPlayer> {
    this.active();
    const player = createPlayer({ playbackMode: 'standard', eventListener: (event: PlayerEvent): void => { this.event(event); } });
    this.player = player;
    await player.attachSurface({ componentId: this.controller.getXComponentSurfaceId(), generation, width: 1280, height: 720 });
    this.active();
    const before = this.firstFrames; this.playerState = 'idle';
    this.record('play-request', String(generation));
    await player.load({ kind: 'localFile', uri: 'file://' + this.root + '/test_video.mp4' },
      (identity: PlayerLoadIdentity): void => { this.record('load-identity', JSON.stringify(identity)); });
    for (let i = 0; i < 100 && this.playerState !== 'preparing' && this.playerState !== 'playing'; i++) await this.delay(50);
    if (this.playerState !== 'playing') await player.play();
    await this.firstFrameAfter(before);
    this.record('open-diagnostics', JSON.stringify(await player.getDiagnostics()));
    this.record('audible-window-start', String(generation));
    return player;
  }
  private number(field: DiagnosticField<number>, allowEstimated: boolean = false): number {
    if (field.status !== 'available' || (field.estimated && !allowEstimated) || field.value === undefined || !Number.isFinite(field.value)) throw new Error('DIAGNOSTIC_UNAVAILABLE');
    return field.value;
  }
  private async badMedia(): Promise<void> {
    const file = fs.openSync(this.root + '/bad.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    fs.writeSync(file.fd, new Uint8Array([0, 1, 2, 3]).buffer); fs.closeSync(file);
    const before = this.errors;
    const player = createPlayer({ playbackMode: 'standard', eventListener: (event: PlayerEvent): void => { this.event(event); } });
    this.player = player;
    await player.attachSurface({ componentId: this.controller.getXComponentSurfaceId(), generation: 1, width: 1280, height: 720 });
    try { await player.load({ kind: 'localFile', uri: 'file://' + this.root + '/bad.mp4' }); }
    catch (_) { this.record('bad-load-rejected'); }
    for (let i = 0; i < 100 && this.errors === before; i++) await this.delay(50);
    if (this.errors === before) throw new Error('BAD_MEDIA_FAILURE_MISSING');
    await player.release(); this.player = undefined;
    this.record('bad-media-returned'); this.errors = 0;
  }
  private async run(): Promise<void> {
    if (this.context === undefined) throw new Error('NO_CONTEXT');
    const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(true);
    this.record('keepScreen', String(w.getWindowProperties().isKeepScreenOn));
    this.status = '标准路径：坏片失败后播放、暂停恢复、seek、关闭重开';
    await this.badMedia();
    const first = await this.open(1); await this.delay(5000);
    this.capture?.assertRecording();
    if (this.focusRequested) await this.focusFlow(first);
    await first.pause(); this.record('pause-start'); await this.delay(1500);
    const paused1 = await first.getDiagnostics(); await this.delay(500); const paused2 = await first.getDiagnostics();
    if (paused2.fields.paused.value !== true || Math.abs(this.number(paused2.fields.positionMs) - this.number(paused1.fields.positionMs)) > 180) throw new Error('PAUSE_NOT_STABLE');
    this.record('pause-verified', JSON.stringify({ before: this.number(paused1.fields.positionMs), after: this.number(paused2.fields.positionMs) }));
    await first.play(); this.record('resume-start'); await this.delay(3000); const resumed = await first.getDiagnostics();
    if (resumed.fields.paused.value !== false || this.number(resumed.fields.positionMs) < this.number(paused2.fields.positionMs) + 300) throw new Error('RESUME_NOT_ADVANCING');
    this.record('resume-verified', String(this.number(resumed.fields.positionMs)));
    const target = 20000;
    if (Math.abs(this.number(resumed.fields.durationMs, true) - 30000) > 100) throw new Error('FIXTURE_DURATION_MISMATCH');
    await first.seekPercent(200 / 3);
    let latest: PlayerDiagnosticsSnapshot = await first.getDiagnostics();
    try {
      await verifySeekProgress({
        snapshot: async (): Promise<SeekSample> => {
          latest = await first.getDiagnostics();
          this.record('seek-sample', JSON.stringify(latest));
          if (latest.fields.paused.status !== 'available' || latest.fields.paused.estimated ||
            latest.fields.buffering.status !== 'available' || latest.fields.buffering.estimated ||
            latest.fields.paused.value === undefined || latest.fields.buffering.value === undefined) {
            throw new Error('DIAGNOSTIC_UNAVAILABLE');
          }
          return { positionMs: this.number(latest.fields.positionMs), paused: latest.fields.paused.value,
            buffering: latest.fields.buffering.value };
        },
        delay: (ms: number): Promise<void> => this.delay(ms),
        record: (event: string, value: string): void => this.record(event, value)
      }, target);
    } catch (error) {
      this.record('seek-failed-diagnostics', JSON.stringify(latest));
      // 失败后的有界观察只帮助定位，不会将本轮失败改判为通过。
      for (let i = 0; i < 20; i++) {
        await this.delay(500);
        this.record('seek-followup', JSON.stringify(await first.getDiagnostics()));
      }
      throw new Error((error as Error).message);
    }
    const snapshot = latest;
    this.record('diagnostics', JSON.stringify({ position: snapshot.fields.positionMs, backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));
    await first.release(); this.record('release-ok'); await this.delay(2500);
    const second = await this.open(2); await this.delay(5000);
    await second.release(); this.record('reopen-release-ok'); await this.delay(2500);
    this.player = undefined;
    this.record('summary', JSON.stringify({ firstFrames: this.firstFrames, errors: this.errors }));
    if (this.errors > 0 || this.firstFrames < 2) throw new Error('PLAYER_EVENT_GATE');
    await this.finish(); this.status = '独立 HAR 正常路径完成';
  }
  private acceptManualResume(): void {
    if (this.awaitingManualResume && !this.cancelled) this.manualResume = true;
  }
  private async focusFlow(player: VidAllPlayer): Promise<void> {
    const alarm = new FocusAlarm((event: string, value: string) => { this.record(event, value); });
    this.alarm = alarm;
    const port: FocusPort = {
      active: (): void => { this.active(); this.capture?.assertRecording(); },
      startAlarm: (): Promise<void> => alarm.start(),
      stopAlarm: (): Promise<void> => alarm.stop(),
      samplesWritten: (): number => alarm.samplesWritten(),
      snapshot: async (): Promise<FocusSnapshot> => {
        const snapshot = await player.getDiagnostics();
        if (snapshot.fields.paused.status !== 'available' || snapshot.fields.paused.estimated ||
          snapshot.fields.paused.value === undefined) throw new Error('PAUSE_DIAGNOSTIC_UNAVAILABLE');
        return { paused: snapshot.fields.paused.value, positionMs: this.number(snapshot.fields.positionMs) };
      },
      delay: (ms: number): Promise<void> => this.delay(ms),
      confirmManualResume: async (): Promise<void> => {
        this.manualResume = false; this.awaitingManualResume = true;
        this.status = '系统打断已解除，请手动继续播放';
        try {
          for (let i = 0; i < 600 && !this.manualResume; i++) await this.delay(200);
          this.active();
          if (!this.manualResume) throw new Error('MANUAL_RESUME_TIMEOUT');
        } finally { this.awaitingManualResume = false; }
      },
      resume: (): Promise<void> => player.play(),
      record: (event: string): void => this.record(event)
    };
    await runFocusProbe(port);
  }
  private async finish(): Promise<void> {
    if (this.context === undefined) return;
    if (this.baseline !== undefined) await this.baseline.close();
    if (this.alarm !== undefined) await this.alarm.stop();
    const player = this.player; this.player = undefined;
    if (player !== undefined && getPlayerRuntimeStatus().state !== 'terminal') await player.release();
    const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(false);
    this.record('keepScreen', String(w.getWindowProperties().isKeepScreenOn));
    if (w.getWindowProperties().isKeepScreenOn) throw new Error('KEEP_SCREEN_NOT_RELEASED');
    this.record('session-end');
  }
  private async fatal(): Promise<void> {
    this.status = '检测到终局，保留应用与日志'; this.record('terminal', JSON.stringify(getPlayerRuntimeStatus()));
    if (this.context !== undefined) {
      const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(false);
    }
  }
  private async copyEvidence(action: string): Promise<void> {
    if (this.cancelled || !this.root) return;
    if (this.chunks === undefined) this.chunks = new EvidenceChunks(this.root, (message: string): void => {
      if (!this.cancelled) this.evidenceStatus = message;
    });
    try {
      if (action === 'next') await this.chunks.next(this.captureBusy);
      else if (action === 'repeat') await this.chunks.repeat(this.captureBusy);
      else await this.chunks.begin(action, this.captureBusy);
    } catch (error) {
      if (!this.cancelled) this.evidenceStatus = '复制失败：' + (error as Error).message;
    }
  }
  private async exportEvidence(kind: string): Promise<void> {
    if (this.evidence === undefined) return;
    try {
      const saved = await this.evidence.exportFile(kind, this.captureBusy);
      if (!this.cancelled) this.evidenceStatus = saved ? '已保存证据文件，仍需核验内容；不等于验收通过' : '已取消保存';
    } catch (error) {
      if (!this.cancelled) this.evidenceStatus = '导出失败：' + (error as Error).message;
    }
  }
  aboutToDisappear(): void { this.cancelled = true; this.evidence?.close(); this.chunks?.close(); this.unsubscribe?.(); this.finish().catch(() => {}); this.capture?.finish().catch(() => {}); }
  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      XComponent({ id: 'p32-video', type: XComponentType.SURFACE, controller: this.controller })
        .width('100%').height('100%')
        .onLoad(() => { this.surface = true; })
      Column() {
      Button('开始系统内录回归').id('audio-capture-start').defaultFocus(true).onClick(() => { this.startCaptured(); })
      Button('系统打断与手动恢复内录').id('audio-focus-start').onClick(() => { this.startCaptured(true); })
      Button('系统播放器同步对照（20秒）').id('audio-baseline-start').onClick(() => { this.startCaptured(false, true); })
      if (this.awaitingManualResume) {
        Button('手动继续播放').id('audio-manual-resume').defaultFocus(true).onClick(() => { this.acceptManualResume(); })
      }
      Row() {
        Button('导出内录').id('audio-export-capture').enabled(!this.captureBusy).onClick(() => { this.exportEvidence('capture'); })
        Button('导出事件').id('audio-export-events').enabled(!this.captureBusy).onClick(() => { this.exportEvidence('events'); })
        Button('导出崩溃').id('audio-export-crash').enabled(!this.captureBusy).onClick(() => { this.exportEvidence('crash'); })
      }
      Row() {
        Button('复制事件').id('audio-copy-events').enabled(!this.captureBusy).onClick(() => { this.copyEvidence('events'); })
        Button('复制内录').id('audio-copy-capture').enabled(!this.captureBusy).onClick(() => { this.copyEvidence('capture'); })
        Button('下一块').id('audio-copy-next').enabled(!this.captureBusy).onClick(() => { this.copyEvidence('next'); })
        Button('重发本块').id('audio-copy-repeat').enabled(!this.captureBusy).onClick(() => { this.copyEvidence('repeat'); })
      }
      Text(this.evidenceStatus).fontSize(16).fontColor(Color.White).backgroundColor('#BB000000')
      Text(this.captureTrace).fontSize(16).fontColor(Color.White).backgroundColor('#BB000000').padding(8)
      Text(this.status).fontSize(24).fontColor(Color.White).backgroundColor('#88000000').padding(16)
      }
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
