import { MediaSource, PlayerSurface } from '../public/types';

// Internal-only contract for a future NAPI implementation; no native handles are public.
export interface NativePlayerBridge {
  attachSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  stop(): Promise<void>;
  release(): Promise<void>;
}
