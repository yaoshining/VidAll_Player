import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { window } from '@kit.ArkUI';
import { createPlayer, VidAllPlayer, initializePlayerRuntime, onPlayerTerminal, getPlayerRuntimeStatus, PlayerEvent, PlayerDiagnosticsSnapshot } from '@vidall/player';
import { SmokePort, SmokeSample } from './SmokeSession';
import { LaunchSession } from './LaunchSession';
export class PlatformPort implements SmokePort {
  private player?: VidAllPlayer;
  private frames: number = 0;
  private errors: number = 0;
  private state: string = 'idle';
  private cycle: number = 0;
  private lastPosition: number = 0;
  private duration: number = 0;
  private measuredCycle: number = 0;
  private unsubscribe?: () => void;
  private context: common.UIAbilityContext;
  private surfaceId: string;
  constructor(context: common.UIAbilityContext, surfaceId: string) { this.context = context; this.surfaceId = surfaceId; }
  now(): number { return Date.now(); }
  sleep(ms: number): Promise<void> { return new Promise<void>((resolve) => { setTimeout(resolve, ms); }); }
  record(event: string, cycle: number, value: string): void { LaunchSession.journal?.record(event, cycle, value); }
  async initialize(): Promise<void> {
    if (LaunchSession.files === undefined) throw new Error('NO_SESSION_DIRECTORY');
    const raw = await this.context.resourceManager.getRawFileContent('test_video.mp4');
    const file = fs.openSync(LaunchSession.files.root + '/test_video.mp4', fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY);
    try { fs.writeSync(file.fd, raw.buffer); } finally { fs.closeSync(file); }
    await initializePlayerRuntime(this.context, { terminalPolicy: 'controlled-app-exit', deadlineMs: 3000 });
    if (getPlayerRuntimeStatus().state !== 'ready') throw new Error('RUNTIME_NOT_READY');
    this.unsubscribe = onPlayerTerminal(() => { this.errors++; this.record('session-failed', this.cycle, 'TERMINAL'); });
  }
  private event(event: PlayerEvent, ownerCycle: number): void {
    if (ownerCycle !== this.cycle || this.player === undefined) return;
    if (event.type === 'firstFrame' && event.surfaceGeneration !== ownerCycle) return;
    if (event.type === 'firstFrame') { this.frames++; this.record('render-observed', this.cycle, JSON.stringify({ generation: event.surfaceGeneration, sequence: event.sequence })); }
    if (event.type === 'state') { this.state = event.state ?? 'unknown'; }
    if (event.type === 'error') { this.errors++; this.record('player-error', this.cycle, event.error?.code ?? 'unknown'); }
  }
  async open(cycle: number): Promise<void> {
    if (this.player !== undefined || LaunchSession.files === undefined) throw new Error('PLAYER_ALREADY_OPEN');
    this.cycle = cycle; this.state = 'idle'; this.lastPosition = 0; this.duration = 0; this.measuredCycle = 0;
    const player = createPlayer({ hardwareDecoding: 'auto', eventListener: (event: PlayerEvent): void => { this.event(event, cycle); } }); this.player = player;
    await player.attachSurface({ componentId: this.surfaceId, generation: cycle, width: 1280, height: 720 });
    await player.load({ kind: 'localFile', uri: 'file://' + LaunchSession.files.root + '/test_video.mp4' });
    for (let i = 0; i < 100 && this.state !== 'preparing' && this.state !== 'playing'; i++) await this.sleep(50);
    if (this.state !== 'playing') await player.play();
  }
  private requirePlayer(): VidAllPlayer { if (this.player === undefined) throw new Error('NO_PLAYER'); return this.player; }
  private sampleGuard(player: VidAllPlayer, cycle: number, checkActive?: () => void): void {
    checkActive?.();
    if (getPlayerRuntimeStatus().state === 'terminal') throw new Error('PLAYER_TERMINAL');
    if (this.player !== player || this.cycle !== cycle) throw new Error('DIAGNOSTICS_RELEASED');
  }
  private async diagnostics(player: VidAllPlayer, cycle: number, checkActive?: () => void): Promise<PlayerDiagnosticsSnapshot> {
    this.sampleGuard(player, cycle, checkActive);
    let snapshot: PlayerDiagnosticsSnapshot;
    try { snapshot = await player.getDiagnostics(); }
    finally { this.sampleGuard(player, cycle, checkActive); }
    if (snapshot.freshness === 'cached-terminal') throw new Error('PLAYER_TERMINAL');
    return snapshot;
  }
  private completedSample(): SmokeSample {
    if (this.measuredCycle !== this.cycle || !Number.isFinite(this.lastPosition) ||
      !Number.isFinite(this.duration) || Math.abs(this.duration - 30000) > 100 ||
      this.lastPosition < 28000 || this.lastPosition > this.duration + 100) throw new Error('EOF_WITHOUT_CYCLE_DIAGNOSTIC');
    return { positionMs: this.lastPosition, durationMs: this.duration, paused: false, completed: true, frames: this.frames, errors: this.errors };
  }
  async sample(checkActive?: () => void): Promise<SmokeSample> {
    checkActive?.();
    if (getPlayerRuntimeStatus().state === 'terminal') throw new Error('PLAYER_TERMINAL');
    const player = this.requirePlayer(); const cycle = this.cycle;
    this.sampleGuard(player, cycle, checkActive);
    if (this.state === 'completed') return this.completedSample();
    let snapshot: PlayerDiagnosticsSnapshot = await this.diagnostics(player, cycle, checkActive);
    this.sampleGuard(player, cycle, checkActive);
    if (this.state === 'completed') return this.completedSample();
    for (let i = 0; i < 50 && (snapshot.fields.positionMs.status !== 'available' || snapshot.fields.durationMs.status !== 'available'); i++) {
      this.sampleGuard(player, cycle, checkActive);
      try { await this.sleep(100); } finally { this.sampleGuard(player, cycle, checkActive); }
      snapshot = await this.diagnostics(player, cycle, checkActive);
      this.sampleGuard(player, cycle, checkActive);
      if (this.state === 'completed') return this.completedSample();
    }
    if (snapshot.fields.positionMs.status !== 'available' || snapshot.fields.positionMs.value === undefined || snapshot.fields.durationMs.status !== 'available' || snapshot.fields.durationMs.value === undefined || snapshot.fields.paused.status !== 'available' || snapshot.fields.paused.value === undefined) throw new Error('DIAGNOSTIC_UNAVAILABLE');
    this.measuredCycle = this.cycle; this.lastPosition = snapshot.fields.positionMs.value; this.duration = snapshot.fields.durationMs.value;
    return { positionMs: this.lastPosition, durationMs: this.duration, paused: snapshot.fields.paused.value, completed: this.state === 'completed', frames: this.frames, errors: this.errors };
  }
  async pause(): Promise<void> { await this.requirePlayer().pause(); }
  async play(): Promise<void> { await this.requirePlayer().play(); }
  async seek(percent: number): Promise<void> { await this.requirePlayer().seekPercent(percent); }
  async release(): Promise<void> {
    if (this.player === undefined) return;
    if (getPlayerRuntimeStatus().state === 'terminal') throw new Error('TERMINAL_RELEASE_FORBIDDEN');
    await this.player.release(); this.player = undefined;
  }
  async keepScreen(enabled: boolean): Promise<boolean> {
    const w = await window.getLastWindow(this.context); await w.setWindowKeepScreenOn(enabled);
    return w.getWindowProperties().isKeepScreenOn;
  }
  dispose(): void { this.unsubscribe?.(); }
}
