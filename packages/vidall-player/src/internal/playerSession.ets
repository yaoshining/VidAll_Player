import {
  ExternalAudio,
  ExternalSubtitle,
  MediaSource,
  PlayerEvent,
  PlayerOptions,
  PlayerSurface,
  PlayerTrack, PlayerTrackKind
} from '../public/types';
import { VidAllPlayer } from '../public/playerContract';
import { CommandQueue } from './commandQueue';
import { validateExternalAudio, validateExternalSubtitle, validateMediaSource } from './inputValidator';
import { NetworkRecoveryController } from './networkRecovery';
import { lifecycleFailure, PlayerFailure } from './playerFailure';
import { ProxyLeaseRecord, ProxyLeaseRegistry } from './proxyLeaseRegistry';
import { redactError } from './redaction';
import { SessionStateMachine } from './stateMachine';

export class PlayerSession implements VidAllPlayer {
  private readonly queue: CommandQueue = new CommandQueue();
  private readonly stateMachine: SessionStateMachine = new SessionStateMachine();
  private readonly leases: ProxyLeaseRegistry = new ProxyLeaseRegistry();
  private readonly recovery: NetworkRecoveryController = new NetworkRecoveryController();
  private surface?: PlayerSurface;
  private source?: MediaSource;
  private tracks: PlayerTrack[] = [];
  private resumeState?: 'playing' | 'paused';
  private leaseEpoch: number = 0;

  constructor(options?: PlayerOptions) {
    if (options?.eventListener !== undefined) {
      this.stateMachine.subscribe(options.eventListener);
    }
  }

  attachSurface(surface: PlayerSurface): Promise<void> {
    return this.enqueue('attachSurface', () => {
      this.validateSurface(surface);
      if (this.surface !== undefined && this.surface.generation === surface.generation &&
        this.surface.width === surface.width && this.surface.height === surface.height) {
        return;
      }
      if (this.surface !== undefined && surface.generation < this.surface.generation) {
        return;
      }
      this.surface = surface;
      this.stateMachine.setSurfaceGeneration(surface.generation);
    });
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    return this.enqueue('resizeSurface', () => {
      this.validateSurface(surface);
      if (this.surface === undefined || surface.generation !== this.surface.generation) {
        throw lifecycleFailure('INVALID_SURFACE_GENERATION', 'Surface generation is not attached.');
      }
      this.surface = surface;
      this.stateMachine.setSurfaceGeneration(surface.generation);
    });
  }

  detachSurface(generation: number): Promise<void> {
    return this.enqueue('detachSurface', () => {
      if (this.surface !== undefined && this.surface.generation === generation) {
        this.surface = undefined;
        this.stateMachine.setSurfaceGeneration(undefined);
      }
    });
  }

  load(source: MediaSource): Promise<void> {
    return this.enqueue('load', () => {
      try {
        validateMediaSource(source);
      } catch (error) {
        const failure: PlayerFailure = error instanceof PlayerFailure ? error : new PlayerFailure({
          domain: 'input',
          code: 'INVALID_MEDIA_SOURCE',
          message: 'Media source validation failed.',
          retryable: false,
          context: {}
        });
        this.stateMachine.transition('error');
        this.stateMachine.emit({ type: 'error', sequence: 0, error: redactError(failure.playerError) });
        throw failure;
      }
      // 串行切源：先终止旧媒体、释放旧 SMB 代理租约并清空轨道与恢复记录，
      // 避免旧连接、旧租约或旧轨道泄漏到新媒体会话。
      this.abortActiveMedia('source-switch');
      this.stateMachine.advanceEventEpoch();
      this.source = source;
      this.tracks = this.createExternalAudioTracks(source.externalAudio).concat(
        this.createExternalSubtitleTracks(source.externalSubtitles, source.externalAudio?.length ?? 0)
      );
      this.recovery.clear();
      this.stateMachine.transition('preparing');
      if (source.kind === 'localhostProxy' && source.proxyLeaseId !== undefined) {
        this.leaseEpoch++;
        const lease = this.leases.track(source.proxyLeaseId, source.uri, this.leaseEpoch);
        if (lease !== undefined) {
          this.emitLease(lease);
        }
      }
      if (this.tracks.length > 0) {
        this.emitTracks();
      }
    });
  }

  play(): Promise<void> {
    return this.enqueue('play', () => {
      const state = this.stateMachine.getState();
      if (state !== 'preparing' && state !== 'paused' && state !== 'buffering') {
        throw lifecycleFailure('INVALID_STATE', 'Play requires prepared, paused, or buffering media.');
      }
      this.stateMachine.transition('playing');
    });
  }

  pause(): Promise<void> {
    return this.enqueue('pause', () => {
      if (this.stateMachine.getState() !== 'playing' && this.stateMachine.getState() !== 'buffering') {
        throw lifecycleFailure('INVALID_STATE', 'Pause requires playing or buffering media.');
      }
      this.stateMachine.transition('paused');
    });
  }

  seekRelative(seconds: number): Promise<void> {
    return this.enqueue('seekRelative', () => this.requireActiveMedia('seekRelative', seconds));
  }

  seekPercent(percent: number): Promise<void> {
    return this.enqueue('seekPercent', () => {
      if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
        throw lifecycleFailure('INVALID_SEEK_PERCENT', '跳转百分比必须是 0 到 100 之间的有限值。Seek percent must be a finite value between 0 and 100.');
      }
      this.requireActiveMedia('seekPercent', percent);
    });
  }

  setRate(rate: number): Promise<void> {
    return this.enqueue('setRate', () => {
      if (!Number.isFinite(rate) || rate <= 0) {
        throw lifecycleFailure('INVALID_RATE', '播放速度必须是大于零的有限值。Playback rate must be a finite value greater than zero.');
      }
      this.requireActiveMedia('setRate', rate);
    });
  }

  setVolume(volume: number): Promise<void> {
    return this.enqueue('setVolume', () => {
      if (!Number.isFinite(volume) || volume < 0 || volume > 100) {
        throw lifecycleFailure('INVALID_VOLUME', '音量必须是 0 到 100 之间的有限值。Volume must be a finite value between 0 and 100.');
      }
    });
  }

  mute(_muted: boolean): Promise<void> {
    return this.enqueue('mute', () => {});
  }

  selectTrack(kind: PlayerTrackKind, id: number | null): Promise<void> {
    return this.enqueue('selectTrack', () => {
      this.requireActiveMedia('selectTrack', id === null ? 0 : id);
      if (id !== null && (!Number.isFinite(id) || !Number.isInteger(id) || id < 0)) {
        throw lifecycleFailure('INVALID_TRACK_ID', '音轨 ID 必须是非负整数。Track id must be a non-negative integer.');
      }
      const candidates = this.tracks.filter((track: PlayerTrack) => track.kind === kind);
      if (id !== null && candidates.every((track: PlayerTrack) => track.id !== id)) {
        throw lifecycleFailure('TRACK_NOT_FOUND', '指定的音轨或字幕轨道不存在。The requested track does not exist.');
      }
      for (let index = 0; index < candidates.length; index++) {
        candidates[index].selected = id !== null && candidates[index].id === id;
      }
      this.emitTracks();
    });
  }

  addExternalAudio(audio: ExternalAudio): Promise<void> {
    return this.enqueue('addExternalAudio', () => {
      this.requireActiveSessionState('addExternalAudio');
      validateExternalAudio(audio);
      this.tracks.push({ id: this.nextTrackId(), kind: 'audio', title: audio.title, language: audio.language, selected: false, recognitionStatus: 'recognized' });
      this.emitTracks();
    });
  }

  addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void> {
    return this.enqueue('addExternalSubtitle', () => {
      // 网络失败或停止后进入 error/idle 状态：source 可能仍存在，但会话已不可
      // 继续编辑轨道，需与 selectTrack/setSubtitleDelay 一致地要求活跃状态。
      this.requireActiveSessionState('addExternalSubtitle');
      validateExternalSubtitle(subtitle);
      const nextId = this.nextTrackId();
      this.tracks.push({
        id: nextId,
        kind: 'subtitle',
        title: subtitle.title,
        selected: false,
        recognitionStatus: subtitle.format === 'pgs' || subtitle.format === 'vobsub' ? 'recognized' : 'renderable'
      });
      this.emitTracks();
    });
  }

  setSubtitleDelay(delayMs: number): Promise<void> {
    return this.enqueue('setSubtitleDelay', () => this.requireActiveMedia('setSubtitleDelay', delayMs));
  }

  subscribe(listener: (event: PlayerEvent) => void): () => void {
    return this.stateMachine.subscribe(listener);
  }

  reportNativeEvent(event: PlayerEvent): boolean {
    return this.stateMachine.emitIncoming(event);
  }

  stop(): Promise<void> {
    return this.enqueue('stop', () => {
      const state = this.stateMachine.getState();
      if (state === 'idle' || state === 'completed' || state === 'error') {
        return;
      }
      if (state !== 'preparing' && state !== 'playing' && state !== 'paused' && state !== 'buffering') {
        throw lifecycleFailure('INVALID_STATE', 'Stop requires an active media session.');
      }
      this.abortActiveMedia('stop');
      this.source = undefined;
    });
  }

  release(): Promise<void> {
    if (this.stateMachine.getReleasePhase() !== 'open') {
      return Promise.resolve();
    }
    this.queue.close();
    return new Promise<void>((resolve) => {
      // 关闭前请求代理释放；只有业务层携带相同 epoch 的确认才能宣布 released。
      this.releaseLeases('release');
      this.stateMachine.release();
      this.surface = undefined;
      this.stateMachine.setSurfaceGeneration(undefined);
      this.source = undefined;
      this.tracks = [];
      resolve();
    });
  }

  // 供原生适配层上报 paused-for-cache / cache-buffering-state：
  // paused=true 进入 buffering 并记住恢复目标，paused=false 恢复原状态。
  reportBuffering(paused: boolean, percent?: number): void {
    if (this.stateMachine.getReleasePhase() !== 'open') {
      return;
    }
    const state = this.stateMachine.getState();
    if (paused) {
      if (state === 'playing' || state === 'paused') {
        this.resumeState = state;
        this.stateMachine.transition('buffering');
        this.emitBuffering(true, percent);
      } else if (state === 'buffering') {
        this.emitBuffering(true, percent);
      }
      return;
    }
    if (state === 'buffering') {
      const resume = this.resumeState === 'paused' ? 'paused' : 'playing';
      this.resumeState = undefined;
      this.stateMachine.transition(resume);
      this.emitBuffering(false, percent);
    }
  }

  // 供原生适配层上报网络失败：清理旧连接/旧媒体状态后进入 error，
  // 事件的 retryable 与稳定码决定消费者重试还是展示不可恢复原因。
  reportNetworkFailure(failure: PlayerFailure): void {
    if (this.stateMachine.getReleasePhase() !== 'open') {
      return;
    }
    const state = this.stateMachine.getState();
    if (state === 'idle' || state === 'released' || state === 'error') {
      return;
    }
    this.recovery.recordFailure(failure);
    if (this.tracks.length > 0) {
      this.tracks = [];
      this.emitTracks();
    }
    this.releaseLeases('network-failure');
    this.resumeState = undefined;
    this.stateMachine.transition('error');
    this.stateMachine.emit({ type: 'error', sequence: 0, error: redactError(failure.playerError) });
  }

  networkRecovery(): NetworkRecoveryController {
    return this.recovery;
  }

  private enqueue(_name: string, operation: () => void): Promise<void> {
    return this.queue.enqueue(() => {
      operation();
      return Promise.resolve();
    });
  }

  private abortActiveMedia(reason: string): void {
    this.releaseLeases(reason);
    if (this.tracks.length > 0) {
      this.tracks = [];
      this.emitTracks();
    }
    this.resumeState = undefined;
    const state = this.stateMachine.getState();
    if (state === 'playing' || state === 'paused' || state === 'buffering' || state === 'preparing') {
      this.stateMachine.transition('idle');
    }
  }

  private releaseLeases(reason: string): void {
    const requested = this.leases.requestReleaseAll(reason);
    for (let index = 0; index < requested.length; index++) {
      this.emitLease(requested[index]);
      this.emitLeaseReleaseRequestedLog(requested[index]);
    }
  }

  private emitLease(record: ProxyLeaseRecord): void {
    this.stateMachine.emit({
      type: 'proxyLease',
      sequence: 0,
      lease: {
        leaseId: record.leaseId,
        state: record.state,
        epoch: record.epoch,
        retryable: record.retryable
      }
    });
  }

  private emitLeaseReleaseRequestedLog(record: ProxyLeaseRecord): void {
    const message = `Proxy lease ${record.leaseId} release requested.`;
    this.stateMachine.emit({
      type: 'log',
      sequence: 0,
      message: message,
      log: { level: 'info', module: 'player-session', message: message }
    });
  }

  private emitBuffering(paused: boolean, percent?: number): void {
    const event: PlayerEvent = { type: 'buffering', sequence: 0, paused: paused };
    if (percent !== undefined && Number.isFinite(percent)) {
      event.percent = percent;
    }
    this.stateMachine.emit(event);
  }

  private createExternalAudioTracks(audioTracks?: ExternalAudio[]): PlayerTrack[] {
    if (audioTracks === undefined) {
      return [];
    }
    const tracks: PlayerTrack[] = [];
    for (let index = 0; index < audioTracks.length; index++) {
      const audio = audioTracks[index];
      tracks.push({
        id: index + 1,
        kind: 'audio',
        title: audio.title,
        language: audio.language,
        selected: false,
        recognitionStatus: 'recognized'
      });
    }
    return tracks;
  }

  private createExternalSubtitleTracks(subtitles?: ExternalSubtitle[], startId: number = 0): PlayerTrack[] {
    if (subtitles === undefined) {
      return [];
    }
    const tracks: PlayerTrack[] = [];
    for (let index = 0; index < subtitles.length; index++) {
      const subtitle = subtitles[index];
      tracks.push({
        id: startId + index + 1,
        kind: 'subtitle',
        title: subtitle.title,
        selected: false,
        recognitionStatus: subtitle.format === 'pgs' || subtitle.format === 'vobsub' ? 'recognized' : 'renderable'
      });
    }
    return tracks;
  }

  private nextTrackId(): number {
    let highestId = 0;
    for (let index = 0; index < this.tracks.length; index++) {
      highestId = Math.max(highestId, this.tracks[index].id);
    }
    return highestId + 1;
  }

  private emitTracks(): void {
    // 深拷贝轨道快照：监听器可能保留事件对象，后续 selected 等字段
    // 变更不能污染已投递事件中的轨道状态。
    const snapshot: PlayerTrack[] = [];
    for (let index = 0; index < this.tracks.length; index++) {
      const track = this.tracks[index];
      const copy: PlayerTrack = {
        id: track.id,
        kind: track.kind,
        selected: track.selected,
        recognitionStatus: track.recognitionStatus
      };
      if (track.language !== undefined) {
        copy.language = track.language;
      }
      if (track.title !== undefined) {
        copy.title = track.title;
      }
      snapshot.push(copy);
    }
    this.stateMachine.emit({ type: 'tracks', sequence: 0, tracks: snapshot });
  }

  private validateSurface(surface: PlayerSurface): void {
    if (surface.componentId.length === 0 || !Number.isFinite(surface.generation) ||
      !Number.isFinite(surface.width) || !Number.isFinite(surface.height) ||
      !Number.isInteger(surface.generation) || surface.generation < 1 ||
      surface.width <= 0 || surface.height <= 0) {
      throw lifecycleFailure('INVALID_SURFACE', 'Surface 必须包含组件 ID、正整数 generation 和有限的正尺寸。Surface must have a component id, a positive integer generation, and finite positive dimensions.');
    }
  }

  private requireActiveSessionState(command: string): void {
    const state = this.stateMachine.getState();
    if (this.source === undefined || (state !== 'preparing' && state !== 'playing' && state !== 'paused' && state !== 'buffering')) {
      throw lifecycleFailure('INVALID_STATE', `${command} 需要已加载的媒体。${command} requires loaded media.`);
    }
  }

  private requireActiveMedia(command: string, value: number): void {
    if (!Number.isFinite(value)) {
      throw lifecycleFailure('INVALID_CONTROL_VALUE', `${command} 需要有限数值。${command} requires a finite value.`);
    }
    this.requireActiveSessionState(command);
  }
}
