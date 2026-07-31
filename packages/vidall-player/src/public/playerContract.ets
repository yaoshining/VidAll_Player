import { ExternalAudio, ExternalSubtitle, MediaSource, PlayerEvent, PlayerSurface, PlayerTrackKind } from './types';

export interface VidAllPlayer {
  attachSurface(surface: PlayerSurface): Promise<void>;
  resizeSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seekRelative(seconds: number): Promise<void>;
  seekPercent(percent: number): Promise<void>;
  setRate(rate: number): Promise<void>;
  setVolume(volume: number): Promise<void>;
  mute(muted: boolean): Promise<void>;
  selectTrack(kind: PlayerTrackKind, id: number | null): Promise<void>;
  addExternalAudio(audio: ExternalAudio): Promise<void>;
  addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void>;
  setSubtitleDelay(delayMs: number): Promise<void>;
  requestCache(uri: string): Promise<void>;
  subscribe(listener: (event: PlayerEvent) => void): () => void;
  stop(): Promise<void>;
  release(): Promise<void>;
}
