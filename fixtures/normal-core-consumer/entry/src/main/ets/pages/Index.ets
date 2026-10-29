import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { window } from '@kit.ArkUI';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, onPlayerTerminal, getPlayerRuntimeStatus, PlayerEvent, DiagnosticField, PlayerDiagnosticsSnapshot } from '@vidall/player';

interface PrivateSmb { uri: string; username: string; password: string; domain?: string; }

@Entry
@Component
struct Index {
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
  private delay(ms: number): Promise<void> { return new Promise<void>((resolve) => { setTimeout(resolve, ms); }); }
  private record(event: string, value: string = ''): void {
    console.info('P32 ' + event + ' ' + value);
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
    this.root = this.context.filesDir + '/phase32-consumer';
    if (!fs.accessSync(this.root)) await fs.mkdir(this.root);
    const data = await this.context.resourceManager.getRawFileContent('test_video.mp4');
    const file = await fs.open(this.root + '/test_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    await fs.write(file.fd, data.buffer); await fs.close(file);
    await initializePlayerRuntime(this.context, { terminalPolicy: 'controlled-app-exit', deadlineMs: 3000 });
    this.record('runtime', getPlayerRuntimeStatus().state);
    this.unsubscribe = onPlayerTerminal(() => { this.fatal().catch(() => { this.record('fatal-ui-error'); }); });
    this.ready = true; this.maybeStart();
  }
  private maybeStart(): void {
    if (!this.ready || !this.surface || this.started) return;
    this.started = true;
    this.run().catch((error: Error) => { this.status = '验证失败'; this.record('failed', error.message); this.finish().catch(() => {}); });
  }
  private async firstFrameAfter(previous: number): Promise<void> {
    for (let i = 0; i < 100 && this.firstFrames <= previous; i++) await this.delay(100);
    if (this.firstFrames <= previous) throw new Error('FIRST_FRAME_TIMEOUT');
  }
  private async open(generation: number): Promise<VidAllPlayer> {
    const player = createPlayer({ hardwareDecoding: 'auto', eventListener: (event: PlayerEvent): void => { this.event(event); } });
    this.player = player;
    await player.attachSurface({ componentId: this.controller.getXComponentSurfaceId(), generation, width: 1280, height: 720 });
    const before = this.firstFrames; this.playerState = 'idle';
    await player.load({ kind: 'localFile', uri: 'file://' + this.root + '/test_video.mp4' });
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
    if (this.context === undefined) throw new Error('NO_CONTEXT');
    const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(true);
    this.record('keepScreen', String(w.getWindowProperties().isKeepScreenOn));
    this.status = '正常核心：播放、暂停恢复、seek、关闭重开';
    const first = await this.open(1); await this.delay(1500);
    await first.pause(); await this.delay(150);
    const paused1 = await first.getDiagnostics(); await this.delay(500); const paused2 = await first.getDiagnostics();
    if (paused2.fields.paused.value !== true || Math.abs(this.number(paused2.fields.positionMs) - this.number(paused1.fields.positionMs)) > 180) throw new Error('PAUSE_NOT_STABLE');
    this.record('pause-verified', JSON.stringify({ before: this.number(paused1.fields.positionMs), after: this.number(paused2.fields.positionMs) }));
    await first.play(); await this.delay(700); const resumed = await first.getDiagnostics();
    if (resumed.fields.paused.value !== false || this.number(resumed.fields.positionMs) < this.number(paused2.fields.positionMs) + 300) throw new Error('RESUME_NOT_ADVANCING');
    this.record('resume-verified', String(this.number(resumed.fields.positionMs)));
    const target = 20000;
    if (Math.abs(this.number(resumed.fields.durationMs) - 30000) > 100) throw new Error('FIXTURE_DURATION_MISMATCH');
    await first.seekPercent(200 / 3);
    let sought: PlayerDiagnosticsSnapshot = await first.getDiagnostics();
    for (let i = 0; i < 20 && Math.abs(this.number(sought.fields.positionMs) - target) > 1500; i++) {
      await this.delay(150); sought = await first.getDiagnostics();
    }
    this.record('seek-target', JSON.stringify({ target, reached: this.number(sought.fields.positionMs) }));
    if (Math.abs(this.number(sought.fields.positionMs) - target) > 1500) throw new Error('SEEK_TARGET_MISMATCH');
    await this.delay(700); const snapshot = await first.getDiagnostics();
    if (this.number(snapshot.fields.positionMs) < this.number(sought.fields.positionMs) + 250) throw new Error('SEEK_NOT_ADVANCING');
    this.record('seek-verified', JSON.stringify({ target, before: this.number(resumed.fields.positionMs), reached: this.number(sought.fields.positionMs), after: this.number(snapshot.fields.positionMs) }));
    this.record('diagnostics', JSON.stringify({ position: snapshot.fields.positionMs, backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));
    await first.release(); this.record('release-ok');
    const second = await this.open(2); await this.delay(1500);
    await this.smbShort(second);
    await second.release(); this.record('reopen-release-ok');
    this.player = undefined;
    this.record('summary', JSON.stringify({ firstFrames: this.firstFrames, errors: this.errors }));
    if (this.errors > 0 || this.firstFrames < 2) throw new Error('PLAYER_EVENT_GATE');
    await this.finish(); this.status = '独立 HAR 正常路径完成';
  }
  private async smbShort(player: VidAllPlayer): Promise<void> {
    const path = this.root + '/credentials.json';
    if (!fs.accessSync(path)) return;
    const credentials: PrivateSmb = JSON.parse(fs.readTextSync(path)) as PrivateSmb;
    fs.unlinkSync(path);
    await player.setPropertyString('msg-level', 'all=no');
    const authorization = 'Basic ' + new util.Base64Helper().encodeToStringSync(new util.TextEncoder().encodeInto(credentials.username + ':' + credentials.password));
    const before = this.firstFrames; this.playerState = 'idle';
    await player.load({kind:'smb',uri:credentials.uri,headers:{authorization}});
    for (let i = 0; i < 100 && this.playerState !== 'preparing' && this.playerState !== 'playing'; i++) await this.delay(50);
    if (this.playerState !== 'playing') await player.play();
    await this.firstFrameAfter(before); await this.delay(1500);
    let a: PlayerDiagnosticsSnapshot = await player.getDiagnostics();
    for (let i = 0; i < 20 && a.fields.positionMs.status !== 'available'; i++) { await this.delay(500); a = await player.getDiagnostics(); }
    this.record('smb-fields', JSON.stringify({position:a.fields.positionMs,decoder:a.fields.hardwareDecoder}));
    await this.delay(1000); const b = await player.getDiagnostics();
    if (this.number(b.fields.positionMs) < this.number(a.fields.positionMs) + 200) throw new Error('SMB_NOT_ADVANCING');
    this.record('smb-short-verified', JSON.stringify({before:this.number(a.fields.positionMs),after:this.number(b.fields.positionMs),decoder:b.fields.hardwareDecoder.value}));
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
    this.status = '播放器无法安全继续，应用将退出，请重新打开'; this.record('terminal');
    if (this.context === undefined) return;
    const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(false);
    await this.delay(800);
    // 终局不能走普通 player.release；原生截止计时独立兜底。
    await this.context.getApplicationContext().killAllProcesses(true);
  }
  aboutToDisappear(): void { this.unsubscribe?.(); this.finish().catch(() => {}); }
  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      XComponent({ id: 'p32-video', type: XComponentType.SURFACE, controller: this.controller })
        .width('100%').height('100%')
        .onLoad(() => { this.surface = true; this.maybeStart(); })
      Text(this.status).fontSize(24).fontColor(Color.White).backgroundColor('#88000000').padding(16)
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
