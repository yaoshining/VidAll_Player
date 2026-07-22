import {
  ExternalSubtitle,
  MediaSource,
  PlayerEvent,
  PlayerOptions,
  PlayerSurface,
  PlayerTrack, PlayerTrackKind
} from '../public/types';
import { VidAllPlayer } from '../public/playerContract';
import { CommandQueue } from './commandQueue';
import { validateMediaSource } from './inputValidator';
import { lifecycleFailure, PlayerFailure } from './playerFailure';
import { redactError } from './redaction';
import { SessionStateMachine } from './stateMachine';

export class PlayerSession implements VidAllPlayer {
  private readonly queue: CommandQueue = new CommandQueue();
  private readonly stateMachine: SessionStateMachine = new SessionStateMachine();
  private surface?: PlayerSurface;
  private source?: MediaSource;

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
    });
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    return this.enqueue('resizeSurface', () => {
      this.validateSurface(surface);
      if (this.surface === undefined || surface.generation !== this.surface.generation) {
        throw lifecycleFailure('INVALID_SURFACE_GENERATION', 'Surface generation is not attached.');
      }
      this.surface = surface;
    });
  }

  detachSurface(generation: number): Promise<void> {
    return this.enqueue('detachSurface', () => {
      if (this.surface !== undefined && this.surface.generation === generation) {
        this.surface = undefined;
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
      this.source = source;
      this.stateMachine.transition('preparing');
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

  setSpeed(speed: number): Promise<void> {
    return this.enqueue('setSpeed', () => {
      if (!Number.isFinite(speed) || speed <= 0) {
        throw lifecycleFailure('INVALID_SPEED', '播放速度必须是大于零的有限值。Playback speed must be a finite value greater than zero.');
      }
      this.requireActiveMedia('setSpeed', speed);
    });
  }

  setVolume(volume: number): Promise<void> {
    return this.enqueue('setVolume', () => {
      if (!Number.isFinite(volume) || volume < 0 || volume > 100) {
        throw lifecycleFailure('INVALID_VOLUME', '音量必须是 0 到 100 之间的有限值。Volume must be a finite value between 0 and 100.');
      }
    });
  }

  setMuted(_muted: boolean): Promise<void> {
    return this.enqueue('setMuted', () => {});
  }

  selectTrack(_kind: PlayerTrackKind, id: number | null): Promise<void> {
    return this.enqueue('selectTrack', () => {
      if (id !== null && (!Number.isFinite(id) || !Number.isInteger(id) || id < 0)) {
        throw lifecycleFailure('INVALID_TRACK_ID', '音轨 ID 必须是非负整数。Track id must be a non-negative integer.');
      }
      this.requireActiveMedia('selectTrack', id === null ? 0 : id);
    });
  }

  addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void> {
    return this.enqueue('addExternalSubtitle', () => {
      if (this.source === undefined) {
        throw lifecycleFailure('INVALID_STATE', 'Adding subtitles requires loaded media.');
      }
      const subtitleKind = subtitle.uri.indexOf('https://') === 0 ? 'https' : 'http';
      validateMediaSource({ kind: subtitleKind, uri: subtitle.uri });
    });
  }

  setSubtitleDelay(delayMs: number): Promise<void> {
    return this.enqueue('setSubtitleDelay', () => this.requireActiveMedia('setSubtitleDelay', delayMs));
  }

  subscribe(listener: (event: PlayerEvent) => void): () => void {
    return this.stateMachine.subscribe(listener);
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
      this.stateMachine.transition('idle');
    });
  }

  release(): Promise<void> {
    if (this.stateMachine.getReleasePhase() !== 'open') {
      return Promise.resolve();
    }
    this.queue.close();
    return new Promise<void>((resolve) => {
      this.stateMachine.release();
      this.surface = undefined;
      this.source = undefined;
      resolve();
    });
  }

  private enqueue(_name: string, operation: () => void): Promise<void> {
    return this.queue.enqueue(() => {
      operation();
      return Promise.resolve();
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

  private requireActiveMedia(command: string, value: number): void {
    if (!Number.isFinite(value)) {
      throw lifecycleFailure('INVALID_CONTROL_VALUE', `${command} 需要有限数值。${command} requires a finite value.`);
    }
    const state = this.stateMachine.getState();
    if (this.source === undefined || (state !== 'preparing' && state !== 'playing' && state !== 'paused' && state !== 'buffering')) {
      throw lifecycleFailure('INVALID_STATE', `${command} 需要已加载的媒体。${command} requires loaded media.`);
    }
  }
}
