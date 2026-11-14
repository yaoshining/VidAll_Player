import raw from 'libraw_capture.so';
import { fileIo as fs } from '@kit.CoreFileKit';
import { deviceInfo } from '@kit.BasicServicesKit';
interface CaptureStatus { state: number; error: number; records?: number; }
export class RawCapture {
  private used: boolean = false;
  private requested: boolean = false;
  private path: string = '';
  private closing?: Promise<void>;
  private record: (event: string, value: string) => void;
  private delay: (ms: number) => Promise<void>;
  constructor(record: (event: string, value: string) => void, delay: (ms: number) => Promise<void>) {
    this.record = record; this.delay = delay;
  }
  public async start(path: string): Promise<void> {
    if (deviceInfo.sdkApiVersion < 19) throw new Error('RAW_API19_REQUIRED');
    if (this.used) throw new Error('RAW_ONE_SHOT');
    this.used = true; this.path = path; this.requested = true;
    this.record('raw-start-requested', await raw.start());
    for (let i = 0; i < 1200; i++) {
      const status = JSON.parse(raw.status()) as CaptureStatus;
      if (status.error !== 0) throw new Error('RAW_ERROR_' + status.error);
      if (status.state === 0) { this.record('raw-started', raw.status()); return; }
      if (status.state !== -1) throw new Error('RAW_STATE_' + status.state);
      await this.delay(50);
    }
    throw new Error('RAW_START_TIMEOUT');
  }
  public assertRecording(): void {
    const status = JSON.parse(raw.status()) as CaptureStatus;
    if (status.error !== 0 || status.state !== 0) throw new Error('RAW_NOT_RECORDING_' + raw.status());
  }
  public finish(): Promise<void> {
    if (this.closing !== undefined) return this.closing;
    this.closing = (async (): Promise<void> => {
      if (!this.requested) return;
      const file = fs.openSync(this.path, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      let result = '';
      try { result = await raw.finish(file.fd); } finally { fs.closeSync(file); }
      this.record('raw-closed', result);
      const status = JSON.parse(result) as CaptureStatus;
      if (status.error !== 0) throw new Error('RAW_FINISH_ERROR_' + status.error);
      if (status.records === undefined || status.records <= 0) throw new Error('RAW_EMPTY');
    })();
    return this.closing;
  }
}
