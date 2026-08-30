export type NativeResultCode =
  'OK' | 'RELEASED' | 'ALREADY_RELEASED' | 'FEATURE_UNSUPPORTED' |
  'NATIVE_PLAYBACK_FAILED' | 'SURFACE_UNAVAILABLE' | 'RENDER_BACKEND_UNAVAILABLE' | 'INPUT_INVALID';

export interface NativeSessionResult {
  ok: boolean;
  handle: number;
  code: NativeResultCode;
}

export interface NativePlayerEvent {
  type: 'state' | 'error' | 'videoParams' | 'audioParams' | 'tracks' | 'subtitleText' | 'position';
  /**
   * 事件载荷，type 不同则格式不同：
   * - videoParams：管道分隔字符串，渐进扩展（末尾新增 renderBackend，不影响既有字段顺序）：
   *   `width|hwdec|pixfmt|bitDepth|primaries|transfer|matrix|videoRange|fps|rotation|aspectRatio|interlaced|colorLevels|bitrate|renderBackend`
   *   - `renderBackend`（最后一位，纯值）映射原生 `RenderBackend` 枚举，反映
   *     `Initialize()` 中 `SelectRenderBackend()` 的实际选择：`vulkan` | `opengles` | `software` | `unavailable`。
   *   - 消费方解析：Dolby Vision 由 `matrix==dolbyvision`（index 6）/`pixfmt`（index 2）识别，
   *     渲染后端取最后一位（`vulkan`=vo_gpu_next 可正常 DV reshape；`opengles`/`software`=render API 不可 reshape）。
   * - audioParams：`samplerate|channels|channelCount|format|bitrate`
   */
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
  createSession(fontsDir?: string, hwdec?: string, toneMapping?: string, hdrComputePeak?: string): NativeSessionResult;
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
  setPropertyString(handle: number, property: string, value: string): NativeSessionResult;
  setAudioFilter(handle: number, filter: string): NativeSessionResult;
  setVolume(handle: number, volume: number): NativeSessionResult;
  selectTrack(handle: number, kind: string, trackId: number): NativeSessionResult;
  addExternalAudio(handle: number, uri: string): NativeSessionResult;
  addExternalSubtitle(handle: number, uri: string): NativeSessionResult;
  setEventCallback(handle: number, callback: (event: NativePlayerEvent) => void): NativeSessionResult;
  getFrameData(handle: number): NativeFrameData | null;
}

declare const nativeSession: NativeSessionModule;
export default nativeSession;
