import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { window } from '@kit.ArkUI';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, getPlayerRuntimeStatus, PlayerEvent,
  DiagnosticField, PlayerDiagnosticsSnapshot, PlayerLoadIdentity, PlayerFaultInfo, onPlayerFault } from '@vidall/player';
import { FenceFaultInbox, FenceProbePort, FenceProbeSession, runFenceProbe } from './FenceRun';

@Entry
@Component
struct Index {
  @State status: string = '准备真实 OHCodec/Vulkan 关闭验证';
  @State visibleSurfaces: number = 1;
  @State awaitingReturn: boolean = false;
  @State listVisible: boolean = false;
  @State awaitingLateClose: boolean = false;
  @State pulseCount: number = 0;
  private controllers: XComponentController[] = [new XComponentController(), new XComponentController(),
    new XComponentController(), new XComponentController()];
  private surfaceReady: boolean[] = [false, false, false, false];
  private players: (VidAllPlayer | undefined)[] = [undefined, undefined, undefined, undefined];
  private identities: (PlayerLoadIdentity | undefined)[] = [undefined, undefined, undefined, undefined];
  private frames: number[] = [0, 0, 0, 0];
  private states: string[] = ['idle', 'idle', 'idle', 'idle'];
  private errors: string[] = ['', '', '', ''];
  private inbox: FenceFaultInbox = new FenceFaultInbox();
  private observerError: string = '';
  private nextRequested: boolean = false;
  private lateCloseConfirmed: boolean = false;
  private ready: boolean = false;
  private started: boolean = false;
  private cancelled: boolean = false;
  private root: string = '';
  private context?: common.UIAbilityContext;
  private faultUnsubscribe?: () => void;
  private heartbeat: number = -1;
  private delay(ms: number): Promise<void> { return new Promise<void>((resolve) => { setTimeout(resolve, ms); }); }
  private active(): void {
    if (this.cancelled) throw new Error('PROBE_CANCELLED');
    if (this.observerError) throw new Error(this.observerError);
    if (getPlayerRuntimeStatus().state !== 'ready') throw new Error('RUNTIME_NOT_READY');
  }
  private record(event: string, value: string = ''): void {
    console.info('P17F ' + event + ' ' + value);
    if (!this.root) return;
    const file = fs.openSync(this.root + '/events.jsonl', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.APPEND);
    fs.writeSync(file.fd, JSON.stringify({ time: Date.now(), event, value }) + '\n'); fs.closeSync(file);
  }
  aboutToAppear(): void {
    this.prepare().catch((error: Error) => { this.status = '准备失败'; this.record('prepare-failed', error.message); });
  }
  private async prepare(): Promise<void> {
    if (this.cancelled) return;
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.root = this.context.filesDir + '/phase17-fence';
    if (!fs.accessSync(this.root)) await fs.mkdir(this.root);
    for (const name of ['global-probe.mp4', 'test_video.mp4']) {
      const data = await this.context.resourceManager.getRawFileContent(name);
      if (this.cancelled) return;
      const file = await fs.open(this.root + '/' + name, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      await fs.write(file.fd, data.buffer); await fs.close(file);
      if (this.cancelled) return;
    }
    await initializePlayerRuntime(this.context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 });
    if (this.cancelled) return;
    // 监听器独立于各 Player；直到整个诊断页退出后才取消。
    this.faultUnsubscribe = onPlayerFault((info: PlayerFaultInfo): void => {
      try { this.inbox.add(info); this.record('runtime-fault', JSON.stringify(info)); }
      catch (error) { this.observerError = (error as Error).message; }
    });
    this.heartbeat = setInterval(() => { this.pulseCount++; }, 200);
    this.record('runtime', getPlayerRuntimeStatus().state);
    this.ready = true; this.maybeStart();
  }
  private maybeStart(): void {
    if (!this.ready || !this.surfaceReady[0] || this.started) return;
    this.started = true;
    this.run().catch((error: Error) => {
      this.status = '验证失败：' + error.message; this.record('failed', error.message);
      this.cancelled = true;
      this.finish().catch((cleanup: Error) => { this.record('cleanup-failed', cleanup.message); });
    });
  }
  private event(index: number, event: PlayerEvent): void {
    if (event.type === 'firstFrame') this.frames[index - 1]++;
    if (event.type === 'state') this.states[index - 1] = event.state ?? 'unknown';
    if (event.type === 'error') this.errors[index - 1] = event.error?.code ?? 'unknown';
    if (event.type === 'firstFrame' || event.type === 'state' || event.type === 'error') {
      this.record('player-event', JSON.stringify({ index, type: event.type, state: event.state,
        code: event.error?.code, surfaceGeneration: event.surfaceGeneration }));
    }
  }
  private async openSession(index: number): Promise<FenceProbeSession> {
    this.active();
    if (this.listVisible) {
      this.status = '视频列表：点击播放另一部视频';
      for (let i = 0; i < 600 && !this.nextRequested; i++) { this.active(); await this.delay(200); }
      this.active();
      if (!this.nextRequested) throw new Error('NEXT_VIDEO_CONFIRM_TIMEOUT');
      this.nextRequested = false; this.listVisible = false;
    }
    this.visibleSurfaces = index;
    for (let i = 0; i < 100 && !this.surfaceReady[index - 1]; i++) { this.active(); await this.delay(50); }
    this.active();
    if (!this.surfaceReady[index - 1]) throw new Error('FRESH_SURFACE_NOT_READY');
    const surfaceId = this.controllers[index - 1].getXComponentSurfaceId();
    const player = createPlayer({ playbackMode: 'standard',
      eventListener: (event: PlayerEvent): void => { this.event(index, event); } });
    this.players[index - 1] = player;
    await player.attachSurface({ componentId: surfaceId, generation: index, width: 1280, height: 720 });
    this.active();
    await player.load({ kind: 'localFile', uri: 'file://' + this.root + (index % 2 ? '/global-probe.mp4' : '/test_video.mp4') },
      (identity: PlayerLoadIdentity): void => {
        this.identities[index - 1] = { sessionId: identity.sessionId, loadGeneration: identity.loadGeneration };
        this.record('load-identity', JSON.stringify({ index, identity: this.identities[index - 1] }));
      });
    this.active();
    for (let i = 0; i < 100 && this.states[index - 1] !== 'preparing' && this.states[index - 1] !== 'playing'; i++) {
      this.active(); await this.delay(50);
    }
    this.active();
    if (this.states[index - 1] !== 'playing') await player.play();
    for (let i = 0; i < 100 && this.frames[index - 1] === 0; i++) { this.active(); await this.delay(100); }
    this.active();
    if (!this.frames[index - 1]) throw new Error('FIRST_FRAME_TIMEOUT');
    if (this.errors[index - 1]) throw new Error('PLAYBACK_ERROR:' + this.errors[index - 1]);
    const identity = this.identities[index - 1];
    if (identity === undefined) throw new Error('LOAD_IDENTITY_REQUIRED');
    this.status = '第 ' + index + ' 个新实例：核对画面与可听音频';
    return { index, surfaceId, identity };
  }
  private async snapshot(session: FenceProbeSession): Promise<PlayerDiagnosticsSnapshot> {
    const player = this.players[session.index - 1];
    if (player === undefined) throw new Error('PLAYER_MISSING');
    return player.getDiagnostics();
  }
  private number(field: DiagnosticField<number>): number {
    if (field.status !== 'available' || field.estimated || field.value === undefined) throw new Error('DIAGNOSTIC_UNAVAILABLE');
    return field.value;
  }
  private async confirmPlayback(session: FenceProbeSession): Promise<void> {
    const before = await this.snapshot(session);
    await this.delay(1500); this.active();
    const after = await this.snapshot(session);
    if (this.errors[session.index - 1]) throw new Error('PLAYBACK_ERROR:' + this.errors[session.index - 1]);
    if (this.number(after.fields.positionMs) < this.number(before.fields.positionMs) + 500) throw new Error('PLAYBACK_NOT_ADVANCING');
    this.record('playback-progress', JSON.stringify({ index: session.index, position: after.fields.positionMs,
      audio: after.fields.audioCodec, audibleAudioAccepted: false }));
  }
  private async closeSession(session: FenceProbeSession): Promise<void> {
    const player = this.players[session.index - 1];
    if (player === undefined) throw new Error('PLAYER_MISSING');
    this.players[session.index - 1] = undefined;
    const started = Date.now(), ticks = this.pulseCount;
    this.status = '关闭第 ' + session.index + ' 个实例，心跳应持续更新';
    await player.release();
    const elapsedMs = Date.now() - started, advanced = this.pulseCount - ticks;
    this.record('release-heartbeat', JSON.stringify({ index: session.index, elapsedMs, ticks: advanced }));
    // 第二次真实 wait 延迟 7 秒，桥在约 5 秒结束接口等待；需观察 UI 仍可运行。
    if (session.index === 2 && advanced < 3) throw new Error('CLOSE_HEARTBEAT_NOT_ADVANCING');
    this.active();
  }
  private async nextFault(sequence: number): Promise<PlayerFaultInfo> {
    for (let i = 0; i < 100; i++) {
      this.active();
      const info = this.inbox.after(sequence);
      if (info !== undefined) return info;
      await this.delay(100);
    }
    throw new Error('INDEPENDENT_CLOSE_FAULT_TIMEOUT');
  }
  private async returnToList(session: FenceProbeSession): Promise<void> {
    this.status = '第 ' + session.index + ' 个视频关闭失败，点击返回列表';
    this.awaitingReturn = true;
    for (let i = 0; i < 600 && this.awaitingReturn; i++) { this.active(); await this.delay(200); }
    if (this.awaitingReturn) throw new Error('RETURN_TO_LIST_TIMEOUT');
    this.record('list-visible-after-fault', String(session.index));
  }
  private acceptReturn(): void {
    if (!this.awaitingReturn || this.cancelled) return;
    this.awaitingReturn = false; this.listVisible = true; this.nextRequested = false;
  }
  private acceptNext(): void {
    if (this.listVisible && !this.cancelled) this.nextRequested = true;
  }
  onBackPress(): boolean {
    if (this.awaitingReturn) { this.acceptReturn(); return true; }
    return this.listVisible;
  }
  private async confirmLateClose(): Promise<void> {
    this.lateCloseConfirmed = false; this.awaitingLateClose = true;
    this.status = '核对本轮同 PID 原生日志：late-close completed real=0';
    for (let i = 0; i < 600 && !this.lateCloseConfirmed; i++) { this.active(); await this.delay(200); }
    this.awaitingLateClose = false;
    if (!this.lateCloseConfirmed) throw new Error('NATIVE_LATE_CLOSE_CONFIRM_TIMEOUT');
    this.record('operator-native-log-confirmed', '需另附同 PID 原始 hilog；下一步仍强制实际 OHCodec/Vulkan');
  }
  private acceptLateClose(): void {
    if (this.awaitingLateClose && !this.cancelled) this.lateCloseConfirmed = true;
  }
  private async run(): Promise<void> {
    const port: FenceProbePort = {
      open: (index: number): Promise<FenceProbeSession> => this.openSession(index),
      close: (session: FenceProbeSession): Promise<void> => this.closeSession(session),
      snapshot: (session: FenceProbeSession): Promise<PlayerDiagnosticsSnapshot> => this.snapshot(session),
      confirmPlayback: (session: FenceProbeSession): Promise<void> => this.confirmPlayback(session),
      returnToList: (session: FenceProbeSession): Promise<void> => this.returnToList(session),
      nextFault: (sequence: number): Promise<PlayerFaultInfo> => this.nextFault(sequence),
      faultCount: (): number => this.inbox.count(),
      runtimeState: (): string => { this.active(); return getPlayerRuntimeStatus().state; },
      confirmLateClose: (): Promise<void> => this.confirmLateClose(),
      record: (event: string, value?: string): void => this.record(event, value)
    };
    await runFenceProbe(port);
    await this.finish();
    this.active();
    if (this.inbox.count() !== 2) throw new Error('UNEXPECTED_FAULT_COUNT');
    this.record('summary', JSON.stringify({ scope: 'real-close-wait', runtime: getPlayerRuntimeStatus().state,
      faults: this.inbox.count(), firstFrames: this.frames, nativeLogAndAudibleAudioAcceptance: 'pending-evidence-review' }));
    this.status = '流程门槛完成；仍须审阅同 PID 日志、画面和可听音频证据';
  }
  private async finish(): Promise<void> {
    for (let i = 0; i < this.players.length; i++) {
      const player = this.players[i]; this.players[i] = undefined;
      if (player !== undefined) await player.release();
    }
    if (this.context !== undefined) {
      const current = await window.getLastWindow(this.context);
      await current.setWindowKeepScreenOn(false);
      this.record('keepScreen', String(current.getWindowProperties().isKeepScreenOn));
      if (current.getWindowProperties().isKeepScreenOn) throw new Error('KEEP_SCREEN_NOT_RELEASED');
    }
  }
  aboutToDisappear(): void {
    this.cancelled = true; this.faultUnsubscribe?.();
    if (this.heartbeat >= 0) { clearInterval(this.heartbeat); this.heartbeat = -1; }
    this.finish().catch((error: Error) => { this.record('cleanup-failed', error.message); });
  }
  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      // 整轮保留旧组件；不得将隔离实例仍持有的窗口交给下一实例。
      XComponent({ id: 'p17-fence-a', type: XComponentType.SURFACE, controller: this.controllers[0] })
        .width('100%').height('100%').onLoad(() => { this.surfaceReady[0] = true; this.maybeStart(); })
      if (this.visibleSurfaces >= 2) {
        XComponent({ id: 'p17-fence-b', type: XComponentType.SURFACE, controller: this.controllers[1] })
          .width('100%').height('100%').onLoad(() => { this.surfaceReady[1] = true; })
      }
      if (this.visibleSurfaces >= 3) {
        XComponent({ id: 'p17-fence-c', type: XComponentType.SURFACE, controller: this.controllers[2] })
          .width('100%').height('100%').onLoad(() => { this.surfaceReady[2] = true; })
      }
      if (this.visibleSurfaces >= 4) {
        XComponent({ id: 'p17-fence-d', type: XComponentType.SURFACE, controller: this.controllers[3] })
          .width('100%').height('100%').onLoad(() => { this.surfaceReady[3] = true; })
      }
      Column({ space: 12 }) {
        Text(this.status).fontSize(22).fontColor(Color.White)
        Text('UI 心跳：' + this.pulseCount).fontSize(18).fontColor(Color.White)
        if (this.awaitingReturn) {
          Button('返回视频列表').focusable(true).defaultFocus(true).onClick(() => { this.acceptReturn(); })
        }
        if (this.listVisible) {
          Text('视频列表（诊断）').fontSize(24).fontColor(Color.White)
          Button('播放另一部视频').focusable(true).defaultFocus(true).onClick(() => { this.acceptNext(); })
        }
        if (this.awaitingLateClose) {
          Button('已核对本轮同 PID 的晚关闭完成日志').focusable(true).defaultFocus(true).onClick(() => { this.acceptLateClose(); })
        }
      }.padding(16).backgroundColor('#CC000000')
    }.width('100%').height('100%').backgroundColor(Color.Black)
  }
}
