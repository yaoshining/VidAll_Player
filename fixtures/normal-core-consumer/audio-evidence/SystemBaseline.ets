import { media } from '@kit.MediaKit';
import { fileIo as fs } from '@kit.CoreFileKit';

// 仅验收对照，独立系统播放器不进入Player HAR，也不作为生产降级路径。
export class SystemBaseline {
  private player?: media.AVPlayer;
  private file?: fs.File;
  private cleanup?: Promise<void>;
  private closing: boolean = false;
  private failure: string = '';
  private record: (event: string, value: string) => void;
  private delay: (ms: number) => Promise<void>;
  constructor(record: (event: string, value: string) => void,
    delay: (ms: number) => Promise<void>) { this.record = record; this.delay = delay; }

  private active(): void {
    if (this.closing) throw new Error('BASELINE_CANCELLED');
    if (this.failure) throw new Error(this.failure);
  }
  private async waitState(state: string): Promise<void> {
    for (let i = 0; i < 100; i++) {
      this.active();
      if (this.player?.state === state) return;
      await this.delay(50);
    }
    throw new Error('BASELINE_STATE_TIMEOUT_' + state);
  }
  public async run(path: string, surfaceId: string): Promise<void> {
    if (!surfaceId) throw new Error('BASELINE_SURFACE_MISSING');
    this.active();
    try {
      const player = await media.createAVPlayer(); this.player = player; this.active();
      player.on('stateChange', (state: string): void => { this.record('baseline-state', state); });
      player.on('error', (error: Error): void => { this.failure = 'BASELINE_ERROR_' + error.message; this.record('baseline-error', this.failure); });
      player.on('timeUpdate', (position: number): void => { this.record('baseline-position', String(position)); });
      this.file = fs.openSync(path, fs.OpenMode.READ_ONLY);
      player.fdSrc = { fd: this.file.fd, offset: 0, length: fs.statSync(this.file.fd).size };
      await this.waitState('initialized');
      player.surfaceId = surfaceId;
      await player.prepare(); this.active();
      this.record('baseline-play-request', '');
      await player.play(); await this.waitState('playing');
      this.record('baseline-window-start', '');
      await this.delay(20000); this.active();
      this.record('baseline-window-end', '');
    } finally { await this.close(); }
  }
  public close(): Promise<void> {
    this.closing = true;
    if (this.cleanup !== undefined) return this.cleanup;
    const player = this.player;
    if (player === undefined) return Promise.resolve();
    this.cleanup = player.release().then(() => {
      this.player = undefined;
      if (this.file !== undefined) { fs.closeSync(this.file); this.file = undefined; }
      this.record('baseline-released', '');
    });
    return this.cleanup;
  }
}
