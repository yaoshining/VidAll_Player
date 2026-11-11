import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { window } from '@kit.ArkUI';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, onPlayerTerminal, getPlayerRuntimeStatus, PlayerEvent, DiagnosticField, PlayerDiagnosticsSnapshot, PlayerLoadIdentity, PlayerFaultInfo, onPlayerFault } from '@vidall/player';


@Entry
@Component
struct Index {
  @State recoverySurfaceVisible: boolean = false;
  private recoverySurfaceReady: boolean = false;
  private recoveryController: XComponentController = new XComponentController();
  @State status: string = '准备独立 HAR 验证';
  private controller: XComponentController = new XComponentController();
  private player?: VidAllPlayer;
  private ready: boolean = false;
  private surface: boolean = false;
  private started: boolean = false;
  private firstFrames: number = 0;
  private playerState: string = 'idle';
  private errors: number = 0;
  private root: string = '';
  private context?: common.UIAbilityContext;
  private unsubscribe?: () => void;
  private faultUnsubscribe?: () => void;
  private firstIdentity?: PlayerLoadIdentity;
  private fault?: PlayerFaultInfo;
  private delay(ms: number): Promise<void> { return new Promise<void>((resolve) => { setTimeout(resolve, ms); }); }
  private record(event: string, value: string = ''): void {
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
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.root = this.context.filesDir + '/phase17-recovery';
    if (!fs.accessSync(this.root)) await fs.mkdir(this.root);
    const data = await this.context.resourceManager.getRawFileContent('test_video.mp4');
    const file = await fs.open(this.root + '/test_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    await fs.write(file.fd, data.buffer); await fs.close(file);
    const firstData = await this.context.resourceManager.getRawFileContent('global-probe.mp4');
    const firstFile = await fs.open(this.root + '/global-probe.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    await fs.write(firstFile.fd, firstData.buffer); await fs.close(firstFile);
    await initializePlayerRuntime(this.context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 });
    this.record('runtime', getPlayerRuntimeStatus().state);
    this.unsubscribe = onPlayerTerminal(() => { this.fatal().catch(() => { this.record('fatal-ui-error'); }); });
    this.faultUnsubscribe = onPlayerFault((info: PlayerFaultInfo): void => { this.fault = info; this.record('fault', JSON.stringify(info)); });
    this.ready = true; this.maybeStart();
  }
  private maybeStart(): void {
    if (!this.ready || !this.surface || this.started) return;
    this.started = true;
    this.run().catch((error: Error) => { this.status = '验证失败'; this.record('failed', error.message); this.finish().catch((error: Error) => { this.record('cleanup-failed', error.message); }); });
  }
  private async firstFrameAfter(previous: number): Promise<void> {
    for (let i = 0; i < 100 && this.firstFrames <= previous; i++) await this.delay(100);
    if (this.firstFrames <= previous) throw new Error('FIRST_FRAME_TIMEOUT');
  }
  private async open(generation: number): Promise<VidAllPlayer> {
    const player = createPlayer({ playbackMode: 'compatible', eventListener: (event: PlayerEvent): void => { this.event(event); } });
    this.player = player;
    await player.attachSurface({ componentId: (generation === 1 ? this.controller : this.recoveryController).getXComponentSurfaceId(), generation, width: 1280, height: 720 });
    const before = this.firstFrames; this.playerState = 'idle';
    await player.load({ kind: 'localFile', uri: 'file://' + this.root + (generation === 1 ? '/global-probe.mp4' : '/test_video.mp4') },
      (identity: PlayerLoadIdentity): void => { this.record('load-identity', JSON.stringify(identity)); if (generation === 1) this.firstIdentity = identity; });
    for (let i = 0; i < 100 && this.playerState !== 'preparing' && this.playerState !== 'playing'; i++) await this.delay(50);
    if (this.playerState !== 'playing') await player.play();
    await this.firstFrameAfter(before);
    return player;
  }
  private number(field: DiagnosticField<number>): number {
    if (field.status !== 'available' || field.value === undefined) throw new Error('DIAGNOSTIC_UNAVAILABLE');
    return field.value;
  }
  private async run(): Promise<void> {
    this.status = '诊断包：验证全局终局后同进程续播';
    const first = await this.open(1);
    this.record('before-global-first-frame');
    for (let i = 0; i < 150 && getPlayerRuntimeStatus().state !== 'terminal'; i++) await this.delay(100);
    if (getPlayerRuntimeStatus().state !== 'terminal') throw new Error('GLOBAL_PROBE_NOT_FIRED');
    this.record('terminal-status', JSON.stringify(getPlayerRuntimeStatus()));
    for (let i = 0; i < 100 && getPlayerRuntimeStatus().recovery?.state !== 'ready'; i++) await this.delay(100);
    if (getPlayerRuntimeStatus().recovery?.state !== 'ready') throw new Error('RECOVERY_NOT_READY');
    this.record('recovery-ready', JSON.stringify(getPlayerRuntimeStatus()));
    for (let i = 0; i < 20 && this.fault === undefined; i++) await this.delay(100);
    if (this.firstIdentity === undefined || this.fault?.attribution.state !== 'known' ||
      this.fault.attribution.sessionId !== this.firstIdentity.sessionId ||
      this.fault.attribution.loadGeneration !== this.firstIdentity.loadGeneration) throw new Error('FAULT_IDENTITY_MISMATCH');
    let oldRejected = false;
    try { await first.play(); } catch (error) {
      if ((error as Error).message !== 'PLAYER_TERMINAL') throw new Error('UNEXPECTED_OLD_ERROR: ' + (error as Error).message);
      oldRejected = true;
    }
    if (!oldRejected) throw new Error('OLD_SESSION_REUSED');
    let releaseRejected = false;
    try { await first.release(); } catch (error) {
      if ((error as Error).message !== 'PLAYER_TERMINAL') throw new Error('UNEXPECTED_OLD_ERROR: ' + (error as Error).message);
      releaseRejected = true; this.record('old-release-rejected', (error as Error).message);
    }
    if (!releaseRejected) throw new Error('OLD_SESSION_RELEASE_FALSE_SUCCESS');
    this.player = undefined;
    this.recoverySurfaceVisible = true;
    for (let i = 0; i < 100 && !this.recoverySurfaceReady; i++) await this.delay(50);
    if (!this.recoverySurfaceReady || this.controller.getXComponentSurfaceId() === this.recoveryController.getXComponentSurfaceId()) throw new Error('FRESH_SURFACE_MISSING');
    this.record('fresh-surface-ready');
    this.record('returned-after-global'); this.errors = 0;
    const second = await this.open(2); await this.delay(700);
    const before = await second.getDiagnostics(); await this.delay(1200);
    const after = await second.getDiagnostics();
    if (this.number(after.fields.positionMs) < this.number(before.fields.positionMs) + 500) throw new Error('RECOVERY_NOT_ADVANCING');
    this.record('recovery-playback', JSON.stringify({ position: after.fields.positionMs,
      backend: after.fields.renderBackend, decoder: after.fields.hardwareDecoder, audio: after.fields.audioCodec }));
    await second.release(); this.record('recovery-release');
    const third = await this.open(3); await this.delay(700); await third.release(); this.player = undefined;
    if (getPlayerRuntimeStatus().state !== 'terminal') throw new Error('GLOBAL_LATCH_RESET');
    this.record('summary', JSON.stringify({ firstFrames: this.firstFrames, errors: this.errors, recovery: getPlayerRuntimeStatus().recovery }));
    if (this.errors || this.firstFrames !== 3) throw new Error('RECOVERY_EVENT_GATE');
    await this.finish(); this.status = '诊断包：同进程兼容续播完成';
  }
  private async finish(): Promise<void> {
    if (this.context === undefined) return;
    if (this.player !== undefined && getPlayerRuntimeStatus().state !== 'terminal') await this.player.release();
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
  aboutToDisappear(): void { this.unsubscribe?.(); this.faultUnsubscribe?.(); this.finish().catch((error: Error) => { this.record('cleanup-failed', error.message); }); }
  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      XComponent({ id: 'p32-video', type: XComponentType.SURFACE, controller: this.controller })
        .width('100%').height('100%')
        .onLoad(() => { this.surface = true; this.maybeStart(); })
      if (this.recoverySurfaceVisible) {
        XComponent({ id: 'p17-recovery-video', type: XComponentType.SURFACE, controller: this.recoveryController })
          .width('100%').height('100%')
          .onLoad(() => { this.recoverySurfaceReady = true; })
      }
      Text(this.status).fontSize(24).fontColor(Color.White).backgroundColor('#88000000').padding(16)
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
