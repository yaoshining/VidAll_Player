export type PlayerState = 'idle' | 'preparing' | 'playing' | 'paused' |
  'buffering' | 'completed' | 'error' | 'released';
export type PlayerTrackKind = 'audio' | 'video' | 'subtitle';
export type PlayerEventType = 'state' | 'firstFrame' | 'position' | 'buffering' | 'tracks' |
  'videoParams' | 'audioParams' | 'proxyLease' | 'streamingConfig' | 'log' | 'closed' | 'error' | 'subtitleText';

export interface PlayerSurface {
  componentId: string;
  generation: number;
  width: number;
  height: number;
}

export interface PlayerOptions {
  eventListener?: (event: PlayerEvent) => void;
  // 仅允许通过真实运行时参数报告的高级显示项；裁剪、去隔行和截图固定不支持。
  advancedVideoOptions?: ('rotation' | 'pixelAspectRatio')[];
  // HarmonyOS 沙箱内没有系统 fontconfig，libass 默认的字体查找会失败，导致字幕轨道
  // 被选中但不可见。传入一个真实文件系统目录（应用需预先把字体解包到此目录），
  // 原生层会用它替代 fontconfig 完成字幕字体匹配。省略则不设置任何字体目录。
  subtitleFontsDir?: string;
  // 硬件解码策略。libmpv 编译时已通过 --enable-ohcodec 集成 OHOS 硬件解码后端
  // （链接 libnative_media_vdec.so），由原生层 mpv 的 hwdec 选项驱动。
  // - 'auto'（默认）：优先使用 ohcodec 硬件解码，硬解失败自动回退软件解码；
  // - 'disabled'：强制纯软件解码（兼容性最高，但高分辨率/高码率可能卡顿）。
  // 省略时按 'auto' 处理。硬件解码是否真正生效由 VideoParams.hardwareDecoding 上报。
  hardwareDecoding?: 'auto' | 'disabled';
}

export interface MediaSource {
  kind: 'localFile' | 'http' | 'https' | 'hls' | 'dash' | 'localhostProxy' | 'smb';
  uri: string;
  headers?: Record<string, string>;
  externalAudio?: ExternalAudio[];
  externalSubtitles?: ExternalSubtitle[];
  proxyLeaseId?: string;
}

export interface ExternalAudio {
  uri: string;
  title?: string;
  language?: string;
}

export interface ExternalSubtitle {
  uri: string;
  title?: string;
  format?: 'srt' | 'ass' | 'ssa' | 'webvtt' | 'pgs' | 'vobsub';
}

export interface PlayerTrack {
  id: number;
  kind: PlayerTrackKind;
  language?: string;
  title?: string;
  selected: boolean;
  recognitionStatus: 'recognized' | 'renderable' | 'degraded' | 'unsupported';
}

export interface PlayerError {
  domain: 'input' | 'network' | 'security' | 'media' | 'render' | 'native' | 'lifecycle';
  code: string;
  message: string;
  retryable: boolean;
  context: Record<string, string | number | boolean>;
}

export interface VideoParams {
  width: number;
  height: number;
  pixelFormat?: string;
  rotation?: number;
  pixelAspectRatio?: string;
  decoder?: string;
  hardwareDecoding?: 'active' | 'fallback' | 'unavailable';
}

export interface AudioParams {
  sampleRate?: number;
  channels?: number;
  channelLayout?: string;
  codec?: string;
}

export interface PlayerLog {
  level: 'debug' | 'info' | 'warn' | 'error';
  module: string;
  message: string;
}

export interface ProxyLeaseStatus {
  leaseId: string;
  state: 'acquired' | 'renewed' | 'releaseRequested' | 'released' | 'expired' | 'cleanupFailed';
  epoch: number;
  retryable: boolean;
}

export interface StreamingConfig {
  kind: 'hls' | 'dash';
  networkRecovery: boolean;
  segmentTimelineEnabled: boolean;
}

export interface PlayerEvent {
  type: PlayerEventType;
  sequence: number;
  eventEpoch?: number;
  surfaceGeneration?: number;
  state?: PlayerState;
  positionMs?: number;
  durationMs?: number;
  percent?: number;
  paused?: boolean;
  tracks?: PlayerTrack[];
  params?: VideoParams | AudioParams;
  lease?: ProxyLeaseStatus;
  streamingConfig?: StreamingConfig;
  log?: PlayerLog;
  error?: PlayerError;
  message?: string;
  // 当前播放位置对应的字幕纯文本（已去除 ASS/SRT 标记），来自 mpv "sub-text"
  // 属性；空字符串表示当前无字幕命中。与视频帧内是否真正合成字幕像素无关，
  // 供消费方（entry 调试页、vidall-tv 等）自行绘制字幕 UI 时使用。
  subtitleText?: string;
}
