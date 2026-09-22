// 仅通过 Want 参数 diagnostics79=true 进入的受控真机验收页。
import { createPlayer, VidAllPlayer, PlayerEvent, PlayerTrack, PlayerDiagnosticsSnapshot, PlayerSurface } from '@vidall/player';
import { common } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { hidebug } from '@kit.PerformanceAnalysisKit';
import { validateProbeSnapshot, summarizeTimings, ProbeTimings } from '../player/DiagnosticsProbeChecks';

interface ProbeRecord { name: string; passed: boolean; detail: string; snapshot?: PlayerDiagnosticsSnapshot; }
interface ProbeWindow { name: string; samples: number; cpu: number[]; pssKb: number[]; wall: ProbeTimings; native: ProbeTimings; positionStart?: number; positionEnd?: number; dropsStart?: string; dropsEnd?: string; }
interface ProbeReport { startedAt: number; finishedAt: number; records: ProbeRecord[]; windows: ProbeWindow[]; errors: string[]; firstFrames: number; completed: boolean; }

@Entry
@Component
struct DiagnosticsProbe {
  private controller: XComponentController = new XComponentController();
  private player?: VidAllPlayer;
  private surface?: PlayerSurface;
  private tracks: PlayerTrack[] = [];
  private state: string = 'idle';
  private context?: common.UIAbilityContext;
  private cancelled: boolean = false;
  private report: ProbeReport = { startedAt: Date.now(), finishedAt: 0, records: [], windows: [], errors: [], firstFrames: 0, completed: false };
  @State status: string = '诊断验收准备中';

  aboutToAppear(): void { this.context = getContext(this) as common.UIAbilityContext; }
  aboutToDisappear(): void { this.cancelled = true; if (this.player) void this.player.release(); }
  private delay(ms: number): Promise<void> { return new Promise<void>((resolve) => setTimeout(resolve, ms)); }
  private save(): void {
    if (!this.context) return;
    const file = fs.openSync(`${this.context.filesDir}/diagnostics79.json`, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try { fs.writeSync(file.fd, JSON.stringify(this.report)); } finally { fs.closeSync(file); }
  }
  private record(name: string, passed: boolean, detail: string, snapshot?: PlayerDiagnosticsSnapshot): void {
    this.report.records.push({ name, passed, detail, snapshot });
    this.status = `${name}: ${passed ? '通过' : '失败'} ${detail}`;
    console.info(`Diagnostics79 ${name} ${passed ? 'PASS' : 'FAIL'} ${detail}`);
    this.save();
  }
  private event(event: PlayerEvent): void {
    if (event.state) this.state = event.state;
    if (event.type === 'tracks') this.tracks = event.tracks ?? [];
    if (event.type === 'firstFrame') this.report.firstFrames++;
    if (event.error) this.report.errors.push(event.error.code);
  }
  private async open(uri: string, kind: 'localFile' | 'http', width: number, height: number): Promise<PlayerDiagnosticsSnapshot> {
    if (!this.player) throw new Error('no-player');
    await this.player.load({ kind, uri });
    for (let i = 0; i < 100; i++) {
      if (this.cancelled) throw new Error('cancelled');
      await this.delay(100);
      if (this.state === 'preparing' || this.state === 'paused' || this.state === 'buffering') {
        await this.player.play();
      }
      let s: PlayerDiagnosticsSnapshot;
      try { s = await this.player.getDiagnostics(); } catch (e) {
        if ((e as Error).message === 'DIAGNOSTICS_STALE') continue;
        throw new Error((e as Error).message);
      }
      if (s.fields.positionMs.status === 'available' && (width === 0 || s.fields.videoInputWidth.value === width)) {
        await this.delay(700);
        const ready = await this.player.getDiagnostics();
        const failures = width > 0 ? validateProbeSnapshot(ready, width, height) : [];
        if (failures.length) throw new Error(failures.join(','));
        return ready;
      }
    }
    throw new Error('media-ready-timeout');
  }
  private async window(name: string, sampling: boolean): Promise<void> {
    if (!this.player) return;
    const start = await this.player.getDiagnostics();
    const cpu: number[] = [], memory: number[] = [], wall: number[] = [], native: number[] = [];
    for (let i = 0; i < 15; i++) {
      await this.delay(1000);
      if (this.cancelled) throw new Error('cancelled');
      cpu.push(hidebug.getCpuUsage()); memory.push(Number(hidebug.getAppNativeMemInfo().pss));
      if (sampling) { const before = Date.now(); const s = await this.player.getDiagnostics(); wall.push(Date.now() - before); native.push(s.collectionDurationMs); }
    }
    const end = await this.player.getDiagnostics();
    this.report.windows.push({name, samples: wall.length, cpu, pssKb: memory, wall: summarizeTimings(wall), native: summarizeTimings(native),
      positionStart: start.fields.positionMs.value, positionEnd: end.fields.positionMs.value,
      dropsStart: start.fields.outputDroppedFrames.value, dropsEnd: end.fields.outputDroppedFrames.value });
    this.record(name, (end.fields.positionMs.value ?? 0) > (start.fields.positionMs.value ?? 0), '15 秒窗口完成', end);
  }
  private async run(): Promise<void> {
    if (!this.context) return;
    try {
      const cache = this.context.cacheDir;
      this.player = createPlayer({ eventListener: (e: PlayerEvent) => this.event(e) });
      this.surface = {componentId: this.controller.getXComponentSurfaceId(), generation: 1, width: 1280, height: 720};
      await this.player.attachSurface(this.surface);
      const idle = await this.player.getDiagnostics(); this.record('idle', idle.fields.positionMs.status !== 'available', '未加载不伪造媒体值', idle);
      const local = await this.open(`file://${cache}/diagnostics79-dual.mp4`, 'localFile', 640, 360);
      this.record('local', local.fields.audioInputSampleRate.value === 48000 && local.fields.mediaFps.value === 25, 'H264 640x360 25fps / AAC 48kHz 双音轨', local);
      await this.window('sampling-off-before', false); await this.window('sampling-on', true); await this.window('sampling-off-after', false);
      await this.player.pause(); await this.delay(400);
      const paused = await this.player.getDiagnostics(); await this.delay(500); const paused2 = await this.player.getDiagnostics();
      this.record('pause', paused2.fields.paused.value === true && Math.abs((paused.fields.positionMs.value ?? 0) - (paused2.fields.positionMs.value ?? 0)) < 100, '暂停位置稳定', paused2);
      await this.player.play(); await this.delay(500);
      const resumed = await this.player.getDiagnostics(); this.record('resume', resumed.fields.paused.value === false, '恢复播放', resumed);
      await this.player.seekPercent(20); await this.delay(700);
      const seek = await this.player.getDiagnostics(); this.record('seek', (seek.fields.progressPercent.value ?? 100) < 30, '跳转至 20%', seek);
      const audio = this.tracks.filter((t: PlayerTrack) => t.kind === 'audio');
      if (audio.length >= 2) { await this.player.selectTrack('audio', audio[1].id); await this.delay(500); const switched = await this.player.getDiagnostics(); this.record('audio-switch', switched.fields.audioInputChannels.value === 1, '第二音轨为单声道', switched); }
      else this.record('audio-switch', false, '未发现两条音轨');
      const network = await this.open('http://127.0.0.1:18779/diagnostics79-dual.mp4', 'http', 640, 360);
      this.record('network', network.mediaGeneration > local.mediaGeneration && network.fields.cacheForwardBytes.status === 'available' && network.fields.cacheTotalBytes.status === 'available' && network.fields.cacheDiskBytes.status === 'unavailable', '受控 HTTP 经 HDC reverse TCP', network);
      await this.player.setPropertyString('cache', 'no'); await this.delay(400);
      const noCache = await this.player.getDiagnostics(); this.record('cache-off', noCache.fields.cacheDurationMs.status !== 'error', '关闭缓存后读取不崩溃', noCache);
      const pending = this.player.getDiagnostics(); const stop = this.player.stop();
      try { await pending; this.record('stop-inflight', false, '过期快照未拒绝'); } catch (_) { this.record('stop-inflight', true, '过期请求被拒绝'); } await stop;
      const stopped = await this.player.getDiagnostics(); this.record('stopped', stopped.fields.positionMs.status !== 'available', '停止后旧数据不可用', stopped);
      const silent = await this.open(`file://${cache}/diagnostics79-silent.mp4`, 'localFile', 320, 180);
      this.record('video-only', silent.fields.audioInputSampleRate.status !== 'available', '无音轨', silent);
      const audioOnly = await this.open(`file://${cache}/diagnostics79-audio.m4a`, 'localFile', 0, 0);
      this.record('audio-only', audioOnly.fields.videoInputWidth.status !== 'available', '无视频轨', audioOnly);
      const live = await this.open('http://127.0.0.1:18780/live.ts', 'http', 640, 360);
      this.record('live', (live.fields.durationMs.status !== 'available' || live.fields.durationMs.estimated) && live.fields.fileSizeBytes.status !== 'available', '无长度流：保留 mpv 估算时长，不当成确定总时长', live);
      for (let i = 0; i < 3; i++) await this.open(`file://${cache}/diagnostics79-dual.mp4`, 'localFile', 640, 360);
      this.record('rapid-reopen', true, '三次重开均取得当前代际快照', await this.player.getDiagnostics());
      await this.player.detachSurface(1); this.surface.generation = 2; await this.player.attachSurface(this.surface);
      await this.open(`file://${cache}/diagnostics79-dual.mp4`, 'localFile', 640, 360);
      const rebuilt = await this.player.getDiagnostics(); this.record('surface-rebuild', rebuilt.surfaceGeneration === 2, '表面代际更新', rebuilt);
      await this.player.release();
      try { await this.player.getDiagnostics(); this.record('released', false, '释放后仍可读取'); } catch (_) { this.record('released', true, '释放后拒绝读取'); }
      this.report.completed = true;
    } catch (e) { this.record('probe-error', false, (e as Error).message); }
    finally { if (this.player) await this.player.release(); this.report.finishedAt = Date.now(); this.save(); console.info('Diagnostics79 FINISHED'); }
  }
  build() {
    Column({space:16}) {
      Text('Issue #79 SDK 真机诊断验收').fontSize(28)
      XComponent({id:'diagnostics79-surface',type:XComponentType.SURFACE,controller:this.controller})
        .width(640).height(360).backgroundColor('#000000').onLoad(() => { void this.run(); })
      Text(this.status).fontSize(20)
    }.width('100%').height('100%').justifyContent(FlexAlign.Center)
  }
}
