export type NativeResultCode =
  'OK' | 'RELEASED' | 'ALREADY_RELEASED' | 'FEATURE_UNSUPPORTED' |
  'NATIVE_PLAYBACK_FAILED' | 'SURFACE_UNAVAILABLE' | 'INPUT_INVALID';

export interface NativeSessionResult {
  ok: boolean;
  handle: number;
  code: NativeResultCode;
}

export interface NativePlayerEvent {
  type: 'state' | 'error' | 'videoParams' | 'audioParams' | 'tracks' | 'subtitleText';
  message: string;
  eventEpoch: number;
  sequence: number;
  surfaceGeneration: number;
}

export interface NativeFrameData {
  width: number;
  height: number;
  data: ArrayBuffer;
}

export interface NativeSessionModule {
  createSession(fontsDir?: string, hwdec?: string): NativeSessionResult;
  releaseSession(handle: number): NativeSessionResult;
  attachSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): NativeSessionResult;
  resizeSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): NativeSessionResult;
  detachSurface(handle: number, generation: number): NativeSessionResult;
  load(handle: number, uri: string, headerFields: string, smbUsername: string, smbPassword: string): NativeSessionResult;
  play(handle: number): NativeSessionResult;
  pause(handle: number): NativeSessionResult;
  stop(handle: number): NativeSessionResult;
  seekRelative(handle: number, seconds: number): NativeSessionResult;
  seekPercent(handle: number, percent: number): NativeSessionResult;
  setRate(handle: number, rate: number): NativeSessionResult;
  selectTrack(handle: number, kind: string, trackId: number): NativeSessionResult;
  addExternalAudio(handle: number, uri: string): NativeSessionResult;
  addExternalSubtitle(handle: number, uri: string): NativeSessionResult;
  setEventCallback(handle: number, callback: (event: NativePlayerEvent) => void): NativeSessionResult;
  getFrameData(handle: number): NativeFrameData | null;
}

declare const nativeSession: NativeSessionModule;
export default nativeSession;
