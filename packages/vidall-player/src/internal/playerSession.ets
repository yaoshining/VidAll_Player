import {
  ExternalAudio,
  ExternalSubtitle,
  MediaSource,
  PlayerEvent,
  PlayerOptions,
  PlayerSurface,
  PlayerTrack, PlayerTrackKind,
  VideoParams
} from '../public/types';
import { VidAllPlayer } from '../public/playerContract';
import { CommandQueue } from './commandQueue';
import { validateExternalAudio, validateExternalSubtitle, validateMediaSource } from './inputValidator';
import { NetworkRecoveryController } from './networkRecovery';
import { lifecycleFailure, PlayerFailure } from './playerFailure';
import { ProxyLeaseRecord, ProxyLeaseRegistry } from './proxyLeaseRegistry';
import { redactError } from './redaction';
import { SessionStateMachine } from './stateMachine';
import { createNativePlayerBridge, NativeBridgeEvent, NativePlayerBridge } from '../native/nativeBridge';

export class PlayerSession implements VidAllPlayer {
  private readonly queue: CommandQueue = new CommandQueue();
  private readonly stateMachine: SessionStateMachine = new SessionStateMachine();
  private readonly leases: ProxyLeaseRegistry = new ProxyLeaseRegistry();
  private readonly recovery: NetworkRecoveryController = new NetworkRecoveryController();
  private readonly nativeBridge: NativePlayerBridge;
  private surface?: PlayerSurface;
  private source?: MediaSource;
  private tracks: PlayerTrack[] = [];
  // ETS 侧对外暴露的音轨/字幕 id -> 真实 mpv track-list id 的映射，仅覆盖由原生
  // track-list 事件枚举出的内嵌轨道（见 mergeNativeTracks）；外挂音频/字幕沿用
  // 原有的本地 id 分配方式直接转发给原生层。
  private readonly nativeTrackIdMap: Map<number, number> = new Map();
  private resumeState?: 'playing' | 'paused';
  private leaseEpoch: number = 0;

  constructor(options?: PlayerOptions, nativeBridge?: NativePlayerBridge) {
    this.nativeBridge = nativeBridge ?? createNativePlayerBridge(options?.subtitleFontsDir);
    this.nativeBridge.subscribe((event) => this.handleNativeBridgeEvent(event));
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
      return this.nativeBridge.attachSurface(surface).then(() => {
        this.surface = surface;
        this.stateMachine.setSurfaceGeneration(surface.generation);
      });
    });
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    return this.enqueue('resizeSurface', () => {
      this.validateSurface(surface);
      if (this.surface === undefined || surface.generation !== this.surface.generation) {
        throw lifecycleFailure('INVALID_SURFACE_GENERATION', 'Surface generation is not attached.');
      }
      return this.nativeBridge.resizeSurface(surface).then(() => {
        this.surface = surface;
        this.stateMachine.setSurfaceGeneration(surface.generation);
      });
    });
  }

  detachSurface(generation: number): Promise<void> {
    return this.enqueue('detachSurface', () => {
      if (this.surface !== undefined && this.surface.generation === generation) {
        return this.nativeBridge.detachSurface(generation).then(() => {
          this.surface = undefined;
          this.stateMachine.setSurfaceGeneration(undefined);
        });
      }
      return Promise.resolve();
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
      return this.nativeBridge.load(source).then(() => {
        this.source = source;
        this.tracks = this.createExternalAudioTracks(source.externalAudio).concat(
        this.createExternalSubtitleTracks(source.externalSubtitles, source.externalAudio?.length ?? 0)
      );
      this.recovery.clear();
      if (source.kind === 'localhostProxy' && source.proxyLeaseId !== undefined) {
        this.leaseEpoch++;
        const lease = this.leases.track(source.proxyLeaseId, source.uri, this.leaseEpoch);
        if (lease !== undefined) {
          this.emitLease(lease);
        }
      }
      // HLS/DASH 自适应流分派：原生桥接层需按类型设置 mpv 缓存与 demuxer 选项。
      if (source.kind === 'hls' || source.kind === 'dash') {
        this.emitStreamingConfig(source.kind);
      }
      if (this.tracks.length > 0) {
        this.emitTracks();
      }
      // MediaSource.externalAudio/externalSubtitles 此前只在此处生成了 ETS 侧的
      // PlayerTrack 记录（音轨/字幕在 UI 上"看起来"存在），但从未真正转发给原生
      // mpv 会话（sub-add/audio-add 只有 addExternalSubtitle()/addExternalAudio()
      // 这两个独立 API 会调用）。导致通过 load() 一次性传入外挂字幕/音频时，选中
      // 的轨道在 mpv 里根本不存在，字幕自然无法被解析/渲染。这里在 load 成功后
      // 立即把 source 里声明的外挂音频/字幕逐一推送到原生层，与 addExternalAudio/
      // addExternalSubtitle 走同一条原生命令，保持两条路径行为一致。
      const externalTrackPushes: Promise<void>[] = [];
      if (source.externalAudio !== undefined) {
        for (let index = 0; index < source.externalAudio.length; index++) {
          externalTrackPushes.push(this.nativeBridge.addExternalAudio(source.externalAudio[index].uri));
        }
      }
      if (source.externalSubtitles !== undefined) {
        for (let index = 0; index < source.externalSubtitles.length; index++) {
          externalTrackPushes.push(this.nativeBridge.addExternalSubtitle(source.externalSubtitles[index].uri));
        }
      }
      if (externalTrackPushes.length > 0) {
        return Promise.all(externalTrackPushes).then(() => {});
      }
      return Promise.resolve();
      });
    });
  }

  play(): Promise<void> {
    return this.enqueue('play', () => {
      const state = this.stateMachine.getState();
      if (state !== 'preparing' && state !== 'paused' && state !== 'buffering') {
        throw lifecycleFailure('INVALID_STATE', 'Play requires prepared, paused, or buffering media.');
      }
      return this.nativeBridge.play();
    });
  }

  pause(): Promise<void> {
    return this.enqueue('pause', () => {
      if (this.stateMachine.getState() !== 'playing' && this.stateMachine.getState() !== 'buffering') {
        throw lifecycleFailure('INVALID_STATE', 'Pause requires playing or buffering media.');
      }
      return this.nativeBridge.pause();
    });
  }

  seekRelative(seconds: number): Promise<void> {
    return this.enqueue('seekRelative', () => {
      this.requireActiveMedia('seekRelative', seconds);
      return this.nativeBridge.seekRelative(seconds);
    });
  }

  seekPercent(percent: number): Promise<void> {
    return this.enqueue('seekPercent', () => {
      if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
        throw lifecycleFailure('INVALID_SEEK_PERCENT', '跳转百分比必须是 0 到 100 之间的有限值。Seek percent must be a finite value between 0 and 100.');
      }
      this.requireActiveMedia('seekPercent', percent);
      return this.nativeBridge.seekPercent(percent);
    });
  }

  setRate(rate: number): Promise<void> {
    return this.enqueue('setRate', () => {
      if (!Number.isFinite(rate) || rate <= 0) {
        throw lifecycleFailure('INVALID_RATE', '播放速度必须是大于零的有限值。Playback rate must be a finite value greater than zero.');
      }
      this.requireActiveMedia('setRate', rate);
      return this.nativeBridge.setRate(rate);
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
      // kind === 'subtitle' 且 id === null 表示关闭字幕；映射表命中时说明该 id
      // 来自原生 track-list 枚举，须转发真实 mpv track id，否则按本地 id 直传
      // （外挂音频/字幕在 addExternalAudio/addExternalSubtitle 添加时通常已被
      // mpv 自动选中，这里的直传主要用于后续切换）。
      const nativeTrackId = id === null ? -1 : (this.nativeTrackIdMap.get(id) ?? id);
      const nativeKind: 'audio' | 'subtitle' = kind === 'subtitle' ? 'subtitle' : 'audio';
      return this.nativeBridge.selectTrack(nativeKind, nativeTrackId);
    });
  }

  addExternalAudio(audio: ExternalAudio): Promise<void> {
    return this.enqueue('addExternalAudio', () => {
      this.requireActiveSessionState('addExternalAudio');
      validateExternalAudio(audio);
      this.tracks.push({ id: this.nextTrackId(), kind: 'audio', title: audio.title, language: audio.language, selected: false, recognitionStatus: 'recognized' });
      this.emitTracks();
      return this.nativeBridge.addExternalAudio(audio.uri);
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
      return this.nativeBridge.addExternalSubtitle(subtitle.uri);
    });
  }

  setSubtitleDelay(delayMs: number): Promise<void> {
    return this.enqueue('setSubtitleDelay', () => this.requireActiveMedia('setSubtitleDelay', delayMs));
  }

  requestCache(_uri: string): Promise<void> {
    return this.enqueue('requestCache', () => {
      throw lifecycleFailure('FEATURE_UNSUPPORTED', '缓存请求在首期版本不支持 (Cache requests are not supported in the first release).');
    });
  }

  subscribe(listener: (event: PlayerEvent) => void): () => void {
    return this.stateMachine.subscribe(listener);
  }

  reportNativeEvent(event: PlayerEvent): boolean {
    return this.stateMachine.emitIncoming(event);
  }

  private handleNativeBridgeEvent(event: NativeBridgeEvent): void {
    if (event.type === 'state' && event.message === 'preparing') {
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        this.stateMachine.transition('preparing');
      }
      return;
    }
    if (event.type === 'state' && event.message === 'playing') {
      // 仅当 native RenderLoop 真正成功提交过一次解码帧后才会到达这里，
      // 因此可以安全地把首帧证据转译为公开的 playing 状态与 firstFrame 事件。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration) &&
        this.stateMachine.getState() !== 'playing') {
        this.stateMachine.transition('playing');
        this.stateMachine.emit({ type: 'firstFrame', sequence: event.sequence });
      }
      return;
    }
    if (event.type === 'state' && event.message === 'paused') {
      // native 侧 mpv "pause" 属性变为 true（如调用 pause() 或用户在其他入口暂停），
      // 转译为公开的 paused 状态，使 play()/pause() 的状态机校验能正确匹配。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        const state = this.stateMachine.getState();
        if (state === 'playing' || state === 'buffering') {
          this.stateMachine.transition('paused');
        }
      }
      return;
    }
    if (event.type === 'state' && event.message === 'resumed') {
      // native 侧 mpv "pause" 属性变回 false（暂停后恢复播放），转译为 playing 状态。
      // 与首帧 'playing' 分开处理，避免重复触发 firstFrame 事件。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        const state = this.stateMachine.getState();
        if (state === 'paused' || state === 'buffering') {
          this.stateMachine.transition('playing');
        }
      }
      return;
    }
    if (event.type === 'tracks') {
      // message 编码为原生 track-list 快照（见 napi_init.cpp 的 EncodeTrackList），
      // 上报媒体内嵌的音轨/字幕元数据；此前该属性从未被观察，导致这些轨道对
      // ArkTS 层完全不可见，音轨/字幕选择功能形同虚设。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        this.mergeNativeTracks(event.message);
      }
      return;
    }
    if (event.type === 'videoParams') {
      // message 采用 "宽x高" 字符串编码（原生 Event 结构体未新增字段），
      // 用于让消费方按真实视频宽高比布局，避免 XComponent 拉伸画面。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        const parts = event.message.split('x');
        if (parts.length === 2) {
          const width = Number(parts[0]);
          const height = Number(parts[1]);
          if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
            const params: VideoParams = { width, height };
            this.stateMachine.emit({ type: 'videoParams', sequence: event.sequence, params });
          }
        }
      }
      return;
    }
    if (event.type === 'subtitleText') {
      // message 为 mpv "sub-text" 属性上报的当前字幕纯文本（空字符串表示当前无
      // 字幕命中）。独立于软件渲染合成管线是否把字幕像素画进视频帧，供消费方
      // （entry 调试页、vidall-tv 等）自行绘制字幕 UI、验证字幕解析是否生效。
      if (this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
        this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
        this.stateMachine.emit({ type: 'subtitleText', sequence: event.sequence, subtitleText: event.message });
      }
      return;
    }
    if (event.type === 'error' && this.stateMachine.acceptNativeSequence(event.eventEpoch, event.sequence) &&
      this.stateMachine.matchesNativeContext(event.eventEpoch, event.surfaceGeneration)) {
      this.stateMachine.transition('error');
      this.stateMachine.emit({ type: 'error', sequence: 0, error: redactError({
        domain: 'native', code: 'NATIVE_PLAYBACK_FAILED', message: event.message, retryable: false, context: {}
      }) });
    }
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
      return this.nativeBridge.stop().then(() => {
        this.abortActiveMedia('stop');
        this.source = undefined;
      });
    });
  }

  release(): Promise<void> {
    if (this.stateMachine.getReleasePhase() !== 'open') {
      return Promise.resolve();
    }
    this.queue.close();
    return this.nativeBridge.release().then(() => {
      // Native release completes before the public session publishes closed.
      this.releaseLeases('release');
      this.stateMachine.release();
      this.surface = undefined;
      this.stateMachine.setSurfaceGeneration(undefined);
      this.source = undefined;
      this.tracks = [];
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

  private enqueue(_name: string, operation: () => void | Promise<void>): Promise<void> {
    return this.queue.enqueue(() => Promise.resolve(operation()));
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

  // 原生 track-list 枚举出的内嵌轨道 id 起点，避免与外挂音频/字幕的本地 id
  // （从 1 开始递增，见 nextTrackId）互相碰撞。
  private static readonly NATIVE_TRACK_ID_OFFSET: number = 100000;

  private mergeNativeTracks(encoded: string): void {
    const offset = PlayerSession.NATIVE_TRACK_ID_OFFSET;
    // 移除上一次的内嵌轨道快照，保留仅来自本地外挂音频/字幕逻辑的轨道，
    // 避免原生每次 track-list 变化都重复累积同一批内嵌轨道。
    this.tracks = this.tracks.filter((track: PlayerTrack) => track.id < offset);
    this.nativeTrackIdMap.clear();
    if (encoded.length > 0) {
      const records = encoded.split('\x1e');
      for (let index = 0; index < records.length; index++) {
        const fields = records[index].split('\x1f');
        if (fields.length !== 5) {
          continue;
        }
        const nativeId = Number(fields[0]);
        const kind = fields[1];
        const language = fields[2];
        const title = fields[3];
        const selected = fields[4] === '1';
        if (!Number.isFinite(nativeId) || nativeId < 0 || (kind !== 'audio' && kind !== 'subtitle')) {
          continue;
        }
        const etsId = offset + nativeId;
        const track: PlayerTrack = {
          id: etsId,
          kind: kind as PlayerTrackKind,
          selected: selected,
          recognitionStatus: 'recognized'
        };
        if (language.length > 0) {
          track.language = language;
        }
        if (title.length > 0) {
          track.title = title;
        }
        this.tracks.push(track);
        this.nativeTrackIdMap.set(etsId, nativeId);
      }
    }
    this.emitTracks();
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

  private emitStreamingConfig(kind: string): void {
    const isAdaptive = kind === 'hls' || kind === 'dash';
    this.stateMachine.emit({
      type: 'streamingConfig',
      sequence: 0,
      streamingConfig: {
        kind: kind as 'hls' | 'dash',
        networkRecovery: isAdaptive,
        segmentTimelineEnabled: isAdaptive,
      },
    });
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
