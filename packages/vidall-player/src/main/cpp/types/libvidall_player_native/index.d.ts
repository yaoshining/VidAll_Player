export type NativeResultCode =
  'OK' | 'RELEASED' | 'ALREADY_RELEASED' | 'FEATURE_UNSUPPORTED' |
  'PLAYER_TERMINAL' | 'RUNTIME_NOT_READY' | 'RUNTIME_CONFIG_INVALID' | 'RUNTIME_CONFIG_CONFLICT' | 'RUNTIME_RESOURCE_FAILED' | 'RUNTIME_ABI_MISMATCH' | 'RUNTIME_SMB_FAILED' | 'RUNTIME_TERMINAL_REGISTER_FAILED' | 'RUNTIME_TERMINAL_ENABLE_FAILED' | 'RUNTIME_MONITOR_FAILED' | 'NATIVE_WORK_CANCELLED' | 'NATIVE_WORK_QUEUE_FAILED' | 'NATIVE_PLAYBACK_FAILED' | 'SURFACE_UNAVAILABLE' | 'RENDER_BACKEND_UNAVAILABLE' | 'INPUT_INVALID';

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
   *   - `renderBackend`（最后一位，纯值）反映**实际渲染路径**：`vulkan` | `opengles` | `software` | `unavailable`。
   *     - `vulkan`=vo_gpu_next 可正常 DV reshape；
   *     - `opengles`/`software`=render API（vo_gpu），DV 不可 reshape；其中 `software` 表示实际以 SW 渲染
   *       （OpenGles 无法升级 GL 或硬解未请求时降级为 SW）。
   *   - 消费方解析：Dolby Vision 由 `matrix==dolbyvision`（index 6）/`pixfmt`（index 2）识别，
   *     渲染后端取最后一位（`vulkan` 可 reshape；`opengles`/`software` 不可）。
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
  configureRuntime(filesDir: string, config: string, deadlineMs: number): Promise<NativeSessionResult>;
  getRuntimeStatus(): string;
  rejectRuntimeResources(): NativeSessionResult;
  createSession(fontsDir?: string, hwdec?: string, toneMapping?: string, hdrComputePeak?: string): Promise<NativeSessionResult>;
  releaseSession(handle: number): Promise<NativeSessionResult>;
  attachSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): Promise<NativeSessionResult>;
  resizeSurface(handle: number, surfaceId: string, generation: number, width: number, height: number): Promise<NativeSessionResult>;
  detachSurface(handle: number, generation: number): Promise<NativeSessionResult>;
  load(handle: number, uri: string, headerFields: string, smbUsername: string, smbPassword: string): Promise<NativeSessionResult>;
  play(handle: number): Promise<NativeSessionResult>;
  pause(handle: number): Promise<NativeSessionResult>;
  stop(handle: number): Promise<NativeSessionResult>;
  seekRelative(handle: number, seconds: number): Promise<NativeSessionResult>;
  seekPercent(handle: number, percent: number): Promise<NativeSessionResult>;
  setRate(handle: number, rate: number): Promise<NativeSessionResult>;
  setPropertyString(handle: number, property: string, value: string): Promise<NativeSessionResult>;
  setAudioFilter(handle: number, filter: string): Promise<NativeSessionResult>;
  setVolume(handle: number, volume: number): Promise<NativeSessionResult>;
  selectTrack(handle: number, kind: string, trackId: number): Promise<NativeSessionResult>;
  addExternalAudio(handle: number, uri: string): Promise<NativeSessionResult>;
  addExternalSubtitle(handle: number, uri: string): Promise<NativeSessionResult>;
  setEventCallback(handle: number, callback: (event: NativePlayerEvent) => void): NativeSessionResult;
  getDiagnostics(handle: number): Promise<string>;
  getFrameData(handle: number): NativeFrameData | null;
}

declare const nativeSession: NativeSessionModule;
export default nativeSession;
