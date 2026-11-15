import { audio } from '@kit.AudioKit';
import { deviceInfo, systemDateTime } from '@kit.BasicServicesKit';

// 16格：110定位头、12位单调序号、偶校验。拒绝回绕，避免长录制误配。
export function anchorCode(sequence: number): number[] {
  if (!Number.isInteger(sequence) || sequence < 0 || sequence > 4095) throw new Error('ANCHOR_SEQUENCE');
  const bits: number[] = [1, 1, 0];
  for (let i = 11; i >= 0; i--) bits.push((sequence >> i) & 1);
  let parity = 0;
  for (const bit of bits) parity ^= bit;
  bits.push(parity); return bits;
}

// 校准音与素材440/880Hz分离；只有写PCM，不在回调查询平台或写文件。
export function fillAnchorPcm(pcm: Int16Array, frame: number, accepting: boolean): number {
  pcm.fill(0);
  for (let i = 0; i + 1 < pcm.length; i += 2) {
    const second = Math.floor(frame / 48000);
    if (accepting && second >= 1 && second <= 11 && second % 2 === 1 && frame % 48000 < 4800) {
      const sample = Math.round(6000 * Math.sin(2 * Math.PI * 2200 * frame / 48000));
      pcm[i] = sample; pcm[i + 1] = sample;
    }
    frame++;
  }
  return frame;
}

export class TimeAnchor {
  private renderer?: audio.AudioRenderer;
  private releasePromise?: Promise<void>;
  private closed: boolean = false;
  private accepting: boolean = false;
  private pendingQuery: boolean = false;
  private timer: number = -1;
  private sequence: number = 0;
  private frames: number = 0;
  private failure: string = '';
  private record: (event: string, value: string) => void;
  private paint: (bits: number[]) => void;
  private delay: (ms: number) => Promise<void>;
  constructor(record: (event: string, value: string) => void, paint: (bits: number[]) => void,
    delay: (ms: number) => Promise<void>) { this.record = record; this.paint = paint; this.delay = delay; }
  private active(): void {
    if (this.closed) throw new Error('ANCHOR_CLOSED');
    if (this.failure) throw new Error(this.failure);
  }
  private mono(): number { return systemDateTime.getUptime(systemDateTime.TimeType.ACTIVE, true); }
  public startVisual(): void {
    this.active();
    if (this.timer !== -1) throw new Error('ANCHOR_VISUAL_ONE_SHOT');
    this.tick();
    this.timer = setInterval(() => {
      try { this.tick(); }
      catch (error) {
        this.failure = (error as Error).message; clearInterval(this.timer); this.timer = -1;
        this.record('anchor-failed', JSON.stringify({ reason: this.failure }));
      }
    }, 200);
  }
  private tick(): void {
    this.active(); const bits = anchorCode(this.sequence);
    const beforeMonoNs = this.mono(); const wallMs = Date.now();
    this.paint(bits);
    const afterMonoNs = this.mono();
    this.record('anchor-visual', JSON.stringify({ sequence: this.sequence++, beforeMonoNs, afterMonoNs, wallMs }));
  }
  private async timestamp(renderer: audio.AudioRenderer): Promise<audio.AudioTimestampInfo> {
    this.pendingQuery = true;
    let timeout = -1;
    const query = renderer.getAudioTimestampInfo().then((value: audio.AudioTimestampInfo): audio.AudioTimestampInfo => {
      this.pendingQuery = false; return value;
    }, (error: Error): audio.AudioTimestampInfo => { this.pendingQuery = false; throw new Error(error.message); });
    const deadline = new Promise<audio.AudioTimestampInfo>((_resolve, reject) => {
      timeout = setTimeout(() => { reject(new Error('ANCHOR_TIMESTAMP_TIMEOUT')); }, 2000);
    });
    try { return await Promise.race([query, deadline]); }
    finally { clearTimeout(timeout); }
  }
  public async calibrate(label: string): Promise<void> {
    this.active();
    if (deviceInfo.sdkApiVersion < 19) throw new Error('ANCHOR_API19_REQUIRED');
    if (this.renderer !== undefined) throw new Error('ANCHOR_RENDERER_RETAINED');
    let started = false;
    try {
      const renderer = await audio.createAudioRenderer({
        streamInfo: { samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_48000, channels: audio.AudioChannel.CHANNEL_2,
          sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE, encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW },
        rendererInfo: { usage: audio.StreamUsage.STREAM_USAGE_MUSIC, rendererFlags: 0 }
      });
      this.renderer = renderer; this.releasePromise = undefined; this.active(); this.frames = 0;
      renderer.on('writeData', (data: ArrayBuffer): void => {
        this.frames = fillAnchorPcm(new Int16Array(data), this.frames, this.accepting && !this.closed);
      });
      renderer.on('audioInterrupt', (event: audio.InterruptEvent): void => {
        this.failure = 'ANCHOR_AUDIO_INTERRUPTED';
        this.record('anchor-audio-interrupt', JSON.stringify(event));
      });
      this.record('anchor-audio-plan', JSON.stringify({ label, frequencyHz: 2200, sampleRate: 48000,
        pulseFrames: [48000, 144000, 240000, 336000, 432000, 528000], pulseWidthFrames: 4800 }));
      this.accepting = true; await renderer.start(); started = true; this.active();
      let previousFrame = 0; let previousTimestamp = 0;
      for (let i = 0; i < 12; i++) {
        await this.delay(1000); this.active();
        const beforeMonoNs = this.mono(); const sample = await this.timestamp(renderer); const afterMonoNs = this.mono();
        this.active();
        this.record('anchor-audio-timestamp', JSON.stringify({ label, framePos: sample.framePos,
          timestamp: sample.timestamp, beforeMonoNs, afterMonoNs, writtenFrames: this.frames, wallMs: Date.now() }));
        if (!Number.isFinite(sample.framePos) || !Number.isFinite(sample.timestamp) || sample.framePos <= previousFrame ||
          sample.timestamp <= previousTimestamp || sample.framePos > this.frames) throw new Error('ANCHOR_TIMESTAMP_INVALID');
        previousFrame = sample.framePos; previousTimestamp = sample.timestamp;
      }
    } finally {
      this.accepting = false;
      if (this.pendingQuery) {
        this.failure = 'ANCHOR_QUERY_PENDING_RETAINED';
        this.record('anchor-retained', JSON.stringify({ label, reason: this.failure }));
      } else { await this.releaseRenderer(started); }
    }
    this.record('anchor-audio-completed', JSON.stringify({ label, frames: this.frames }));
  }
  private releaseRenderer(started: boolean): Promise<void> {
    if (this.releasePromise !== undefined) return this.releasePromise;
    const renderer = this.renderer;
    if (renderer === undefined) return Promise.resolve();
    this.releasePromise = (async (): Promise<void> => {
      if (started) await renderer.stop();
      await renderer.release(); this.renderer = undefined;
    })();
    return this.releasePromise;
  }
  public async close(): Promise<void> {
    this.closed = true; this.accepting = false;
    if (this.timer !== -1) { clearInterval(this.timer); this.timer = -1; }
    if (this.pendingQuery) throw new Error('ANCHOR_QUERY_PENDING_RETAINED');
    await this.releaseRenderer(true);
  }
}
