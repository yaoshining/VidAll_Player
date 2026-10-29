// 真实入口和宿主测试共用；观察来自公共播放器API，调用返回不作为播放证据。
export interface SmokeSample { positionMs: number; durationMs: number; paused: boolean; completed: boolean; frames: number; errors: number; }
export interface SmokePort {
  now(): number;
  sleep(ms: number): Promise<void>;
  initialize(): Promise<void>;
  open(cycle: number): Promise<void>;
  sample(checkActive?: () => void): Promise<SmokeSample>;
  pause(): Promise<void>;
  play(): Promise<void>;
  seek(percent: number): Promise<void>;
  release(): Promise<void>;
  keepScreen(enabled: boolean): Promise<boolean>;
  record(event: string, cycle: number, value: string): void;
}
export interface SmokeResult { passed: boolean; cleanupPassed: boolean; error: string; }
export class SmokeSession {
  private started: number = 0;
  private cycle: number = 0;
  private live: boolean = false;
  private cancelled: boolean = false;
  private recordFailed: boolean = false;
  private port: SmokePort;
  private limitMs: number;
  private cleanupMs: number;
  constructor(port: SmokePort, limitMs: number = 120000, cleanupMs: number = 3000) { this.port = port; this.limitMs = limitMs; this.cleanupMs = cleanupMs; }
  cancel(): void { this.cancelled = true; }
  private guard(): void {
    if (this.cancelled) throw new Error('SESSION_CANCELLED');
    if (this.port.now() - this.started > this.limitMs) throw new Error('SESSION_TIMEOUT');
  }
  private async checked(): Promise<SmokeSample> {
    // 最多50次（含首次），仅重采样明确的过期快照；不改变公共API的新鲜度规则。
    const began = this.port.now();
    for (let attempt = 0; attempt < 50; attempt++) {
      this.guard();
      try {
        const s = await this.port.sample((): void => { this.guard(); });
        this.guard();
        if (attempt > 0 && this.port.now() - began >= 5000) throw new Error('DIAGNOSTICS_STALE');
        if (s.errors !== 0) throw new Error('PLAYER_ERROR');
        if (!Number.isFinite(s.positionMs) || !Number.isFinite(s.durationMs) || Math.abs(s.durationMs - 30000) > 100) throw new Error('MEDIA_DURATION');
        return s;
      } catch (failure) {
        this.guard();
        if ((failure as Error).message !== 'DIAGNOSTICS_STALE') throw (failure as Error);
        if (attempt === 49 || this.port.now() - began >= 5000) throw (failure as Error);
      }
      this.guard(); await this.port.sleep(100); this.guard();
      if (this.port.now() - began >= 5000) throw new Error('DIAGNOSTICS_STALE');
    }
    throw new Error('DIAGNOSTICS_STALE');
  }
  private emit(event: string, value: string): void {
    try { this.port.record(event, this.cycle, value); }
    catch (_) { this.recordFailed = true; this.cancelled = true; }
  }
  private async advance(event: string, delayMs: number): Promise<void> {
    const a = await this.checked(); await this.port.sleep(delayMs); const b = await this.checked();
    if (b.paused || b.positionMs < a.positionMs + 500) throw new Error('POSITION_NOT_ADVANCING');
    this.emit(event, JSON.stringify({ beforeMs: a.positionMs, afterMs: b.positionMs, intervalMs: delayMs }));
  }
  private async open(cycle: number, frames: number): Promise<SmokeSample> {
    this.guard(); this.cycle = cycle; this.live = true; await this.port.open(cycle);
    let s = await this.checked();
    for (let i = 0; i < 100 && s.frames <= frames; i++) { await this.port.sleep(100); s = await this.checked(); }
    if (s.frames <= frames) throw new Error('FIRST_FRAME_TIMEOUT');
    this.emit('frame', JSON.stringify({ count: s.frames, positionMs: s.positionMs, evidence: 'public-firstFrame-render-event' }));
    return s;
  }
  private async scenario(): Promise<void> {
    this.guard();
    const enabled = await this.port.keepScreen(true); this.emit('keep-screen', String(enabled));
    if (!enabled) throw new Error('KEEP_SCREEN_NOT_ENABLED');
    await this.port.initialize(); this.emit('runtime-ready', 'ready'); this.guard();
    await this.open(1, 0); await this.advance('progress', 700);
    await this.port.pause(); await this.port.sleep(150); const a = await this.checked(); await this.port.sleep(1000); const b = await this.checked();
    if (!a.paused || !b.paused || Math.abs(b.positionMs - a.positionMs) > 180) throw new Error('PAUSE_NOT_STABLE');
    this.emit('paused', JSON.stringify({ beforeMs: a.positionMs, afterMs: b.positionMs, intervalMs: 1000, paused: true }));
    await this.port.play(); await this.advance('resumed', 700);
    const targetMs = 10000; this.emit('seek-request', JSON.stringify({ targetMs })); await this.port.seek(100 / 3);
    let sought = await this.checked();
    for (let i = 0; i < 30 && Math.abs(sought.positionMs - targetMs) > 1000; i++) { await this.port.sleep(100); sought = await this.checked(); }
    if (Math.abs(sought.positionMs - targetMs) > 1000) throw new Error('SEEK_TARGET_MISMATCH');
    const reachedMs = sought.positionMs; await this.port.sleep(700); sought = await this.checked();
    if (sought.positionMs < reachedMs + 500) throw new Error('SEEK_NOT_ADVANCING');
    this.emit('seek-complete', JSON.stringify({ targetMs, reachedMs, afterMs: sought.positionMs }));
    const frames = sought.frames; await this.port.release(); this.live = false; this.emit('closed', 'released');
    await this.open(2, frames); this.emit('reopened', 'new-first-frame'); await this.advance('progress', 700);
    let ended = await this.checked();
    for (let i = 0; i < 380 && !ended.completed; i++) { await this.port.sleep(100); ended = await this.checked(); }
    if (!ended.completed || ended.positionMs < 28000) throw new Error('EOF_NOT_CONFIRMED');
    this.emit('eof', JSON.stringify({ positionMs: ended.positionMs, durationMs: ended.durationMs, completed: true }));
    await this.port.release(); this.live = false; this.emit('release-complete', 'released');
  }
  private async bounded(action: Promise<void>, limit: number): Promise<void> {
    let timer: number = -1;
    try {
      await Promise.race([action, new Promise<void>((resolve, reject) => { timer = setTimeout(() => { this.cancelled = true; reject(new Error('SESSION_TIMEOUT')); }, limit); })]);
    } finally { if (timer !== -1) clearTimeout(timer); }
  }
  async run(): Promise<SmokeResult> {
    this.started = this.port.now(); let passed = false; let cleanupPassed = true; let error = '';
    try { await this.bounded(this.scenario(), this.limitMs); this.guard(); passed = true; }
    catch (failure) { error = (failure as Error).message; }
    finally {
      // release失败或卡住不能阻止独立尝试关闭窗口保屏。
      if (this.live) {
        try { await this.bounded(this.port.release(), this.cleanupMs); this.live = false; this.emit('release-complete', 'released'); }
        catch (_) { cleanupPassed = false; this.emit('release-failed', 'unconfirmed'); }
      }
      try {
        await this.bounded((async (): Promise<void> => {
          const actual = await this.port.keepScreen(false); this.emit('keep-screen', String(actual));
          if (actual) throw new Error('KEEP_SCREEN_NOT_RELEASED');
        })(), this.cleanupMs);
      } catch (_) { cleanupPassed = false; this.emit('keep-screen-failed', 'unconfirmed'); }
    }
    if (passed && cleanupPassed && !this.cancelled) this.emit('session-end', 'passed');
    else { passed = false; this.emit('session-failed', error || 'CLEANUP_FAILED'); }
    return { passed: passed && !this.recordFailed, cleanupPassed, error: error || (this.recordFailed ? 'JOURNAL_FAILED' : '') };
  }
}
