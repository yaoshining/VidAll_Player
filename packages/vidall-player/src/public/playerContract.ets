import { ExternalSubtitle, MediaSource, PlayerEvent, PlayerSurface, PlayerTrack, PlayerTrackKind } from './types';

export interface VidAllPlayer {
  attachSurface(surface: PlayerSurface): Promise<void>;
  resizeSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seekRelative(seconds: number): Promise<void>;
  seekPercent(percent: number): Promise<void>;
  setSpeed(speed: number): Promise<void>;
  setVolume(volume: number): Promise<void>;
  setMuted(muted: boolean): Promise<void>;
  selectTrack(kind: PlayerTrackKind, id: number | null): Promise<void>;
  addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void>;
  setSubtitleDelay(delayMs: number): Promise<void>;
  subscribe(listener: (event: PlayerEvent) => void): () => void;
  stop(): Promise<void>;
  release(): Promise<void>;
}
