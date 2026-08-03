export type NativeResultCode =
  'OK' | 'RELEASED' | 'ALREADY_RELEASED' | 'FEATURE_UNSUPPORTED' |
  'NATIVE_PLAYBACK_FAILED' | 'SURFACE_UNAVAILABLE' | 'INPUT_INVALID';

export interface NativeSessionResult {
  ok: boolean;
  handle: number;
  code: NativeResultCode;
}

export interface NativePlayerEvent {
  type: 'state' | 'error' | 'videoParams';
  message: string;
  eventEpoch: number;
  sequence: number;
  surfaceGeneration: number;
}

export interface NativeSessionModule {
  createSession(): NativeSessionResult;
  releaseSession(handle: number): NativeSessionResult;
  attachSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): NativeSessionResult;
  resizeSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): NativeSessionResult;
  detachSurface(handle: number, generation: number): NativeSessionResult;
  load(handle: number, uri: string, headerFields: string, smbUsername: string, smbPassword: string): NativeSessionResult;
  play(handle: number): NativeSessionResult;
  pause(handle: number): NativeSessionResult;
  stop(handle: number): NativeSessionResult;
  setEventCallback(handle: number, callback: (event: NativePlayerEvent) => void): NativeSessionResult;
}

declare const nativeSession: NativeSessionModule;
export default nativeSession;
