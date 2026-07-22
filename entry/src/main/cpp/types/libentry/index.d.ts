export interface LibMpvBuildInfo {
  available: boolean;
  abi: string;
  mpvVersion: string;
  sourceCommit: string;
}

export interface FrameData {
  width: number;
  height: number;
  data: ArrayBuffer;
}

export interface LibMpvNapi {
  getBuildInfo(): LibMpvBuildInfo;
  createPlayer(): number;
  attachSurface(handle: number, surfaceId: string): string;
  detachSurface(handle: number): string;
  load(handle: number, url: string): string;
  setPause(handle: number, paused: boolean): string;
  seekRelative(handle: number, seconds: number): string;
  seekPercent(handle: number, percent: number): string;
  setSpeed(handle: number, speed: number): string;
  setVolume(handle: number, volume: number): string;
  setMuted(handle: number, muted: boolean): string;
  stop(handle: number): string;
  release(handle: number): string;
  getPlayerStatus(handle: number): string;
  getFrameData(handle: number): FrameData | null;
}

declare const libentry: LibMpvNapi;
export default libentry;
