import { audio } from '@kit.AudioKit';

// 一次性独立竞争源；只供验收，不链接到正式 Player HAR。
export class FocusAlarm {
  private renderer?: audio.AudioRenderer;
  private startup?: Promise<void>;
  private cleanup?: Promise<void>;
  private cancelled: boolean = false;
  private accepting: boolean = false;
  private started: boolean = false;
  private samples: number = 0;
  private phase: number = 0;
  private record: (event: string, value: string) => void;
  constructor(record: (event: string, value: string) => void) { this.record = record; }
  public samplesWritten(): number { return this.samples; }
  public start(): Promise<void> {
    if (this.startup !== undefined || this.cancelled) return Promise.reject(new Error('ALARM_ONE_SHOT'));
    this.startup = this.open();
    return this.startup;
  }
  private active(): void { if (this.cancelled) throw new Error('ALARM_CANCELLED'); }
  private async open(): Promise<void> {
    this.renderer = await audio.createAudioRenderer({
      streamInfo: { samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_48000, channels: audio.AudioChannel.CHANNEL_2,
        sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE, encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW },
      rendererInfo: { usage: audio.StreamUsage.STREAM_USAGE_ALARM, rendererFlags: 0 }
    });
    this.active();
    const renderer = this.renderer;
    renderer.on('writeData', (data: ArrayBuffer): void => {
      const pcm = new Int16Array(data); pcm.fill(0);
      if (!this.accepting || this.cancelled) return;
      for (let i = 0; i + 1 < pcm.length; i += 2) {
        const sample = Math.round(Math.sin(this.phase) * 3932);
        pcm[i] = sample; pcm[i + 1] = sample;
        this.phase = (this.phase + 2 * Math.PI * 1320 / 48000) % (2 * Math.PI);
        this.samples++;
      }
    });
    renderer.on('audioInterrupt', (event: audio.InterruptEvent): void => { this.record('alarm-interrupt', JSON.stringify(event)); });
    await renderer.setInterruptMode(audio.InterruptMode.INDEPENDENT_MODE);
    this.active(); this.accepting = true;
    this.record('alarm-start-request', String(Date.now()));
    await renderer.start(); this.started = true;
    this.active(); this.record('alarm-started', String(Date.now()));
  }
  public stop(): Promise<void> {
    if (this.cleanup !== undefined) return this.cleanup;
    this.cancelled = true; this.accepting = false;
    this.cleanup = this.close(); return this.cleanup;
  }
  private async close(): Promise<void> {
    if (this.startup !== undefined) { try { await this.startup; } catch (_) {} }
    const renderer = this.renderer;
    if (renderer === undefined) return;
    let failure: string = '';
    if (this.started) {
      try { await renderer.stop(); } catch (error) { failure = (error as Error).message; }
    }
    await renderer.release(); this.renderer = undefined;
    this.record('alarm-stopped', JSON.stringify({ time: Date.now(), samples: this.samples }));
    if (failure) throw new Error(failure);
  }
}
