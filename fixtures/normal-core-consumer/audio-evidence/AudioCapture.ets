import { media } from '@kit.MediaKit';
import { fileIo as fs } from '@kit.CoreFileKit';

// 独立验收工具，一次运行只允许一次录制；不进入 Player HAR。
export class AudioCapture {
  public startedAt: number = 0;
  private recorder?: media.AVScreenCaptureRecorder;
  private file?: fs.File;
  private phase: string = 'idle';
  private failure: string = '';
  private cleanup?: Promise<void>;
  private startup?: Promise<void>;
  private closingRequested: boolean = false;
  private record: (event: string, value: string) => void;
  constructor(record: (event: string, value: string) => void) { this.record = record; }

  private fail(reason: string): void {
    if (!this.failure) this.failure = reason;
    this.record('capture-failed', reason);
  }
  public assertRecording(): void {
    if (this.failure || this.phase !== 'recording') throw new Error(this.failure || 'CAPTURE_NOT_RECORDING');
  }
  public async start(path: string, timeoutMs: number = 15000): Promise<void> {
    if (this.phase !== 'idle') throw new Error('CAPTURE_ONE_SHOT');
    this.phase = 'preparing';
    this.startup = this.open(path, timeoutMs);
    try { await this.startup; }
    catch (error) {
      this.fail((error as Error).message);
      await this.finish();
      throw new Error(this.failure);
    }
  }
  private checkCancelled(): void {
    if (this.closingRequested) throw new Error('CAPTURE_CANCELLED');
  }
  private async open(path: string, timeoutMs: number): Promise<void> {

      this.file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      const recorder = await media.createAVScreenCaptureRecorder();
      this.recorder = recorder;
      this.checkCancelled();
      recorder.on('stateChange', (state: media.AVScreenCaptureStateCode): void => {
        this.record('capture-state', String(state));
        if (this.closingRequested || this.phase === 'closing' || this.phase === 'closed') return;
        if (state === 0 && this.phase === 'starting' && !this.failure) {
          this.startedAt = Date.now(); this.phase = 'recording';
          this.record('capture-started', String(this.startedAt));
        } else if (state !== 0 && state !== 5 && state !== 6 && state !== 7) {
          // 5/6/7 仅表示麦克风状态；本工具明确禁用麦克风。
          // 提前停止、被抢占或隐私窗口都不能继续计作完整证据。
          this.fail('CAPTURE_STATE_' + String(state));
        }
      });
      recorder.on('error', (error: Error): void => { this.fail('CAPTURE_ERROR_' + JSON.stringify(error)); });
      await recorder.init({ fd: this.file.fd, frameWidth: 640, frameHeight: 1024,
        videoBitrate: 1500000, audioSampleRate: 48000, audioChannelCount: 2, audioBitrate: 96000 });
      this.checkCancelled();
      await recorder.setMicEnabled(false);
      this.checkCancelled();
      this.phase = 'starting';
      await recorder.startRecording();
      const deadline = Date.now() + timeoutMs;
      while (this.phase === 'starting' && !this.failure && !this.closingRequested && Date.now() < deadline) {
        await new Promise<void>((resolve) => { setTimeout(resolve, 5); });
      }
      this.checkCancelled();
      if (this.phase !== 'recording' && !this.failure) this.fail('CAPTURE_START_TIMEOUT');
      this.assertRecording();
  }
  public finish(): Promise<void> {
    if (this.cleanup !== undefined) return this.cleanup;
    this.closingRequested = true;
    this.cleanup = this.close();
    return this.cleanup;
  }
  private async close(): Promise<void> {
    if (this.startup !== undefined) {
      try { await this.startup; } catch (error) { this.fail((error as Error).message); }
    }
    const wasActive = this.phase === 'recording' || this.phase === 'starting';
    this.phase = 'closing';
    if (this.recorder !== undefined) {
      if (wasActive) {
        try { await this.recorder.stopRecording(); }
        catch (error) { this.fail((error as Error).message); }
      }
      // release 失败时保留 fd 与 recorder；不重试，也不将不完整文件报为成功。
      await this.recorder.release();
      this.recorder = undefined;
    }
    if (this.file !== undefined) { fs.closeSync(this.file); this.file = undefined; }
    this.phase = 'closed';
    this.record('capture-closed', String(Date.now()));
    if (this.failure) throw new Error(this.failure);
  }
}
