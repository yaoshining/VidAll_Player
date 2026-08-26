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
  // HDR tone mapping 曲线（issue #66）：libmpv 渲染 API 后端（vo_gpu）支持的一组曲线，
  // 决定 HDR10(PQ)/HLG/BT.2020 内容 tone map 到目标显示时的亮度压缩方式。
  // 缺省为 'bt.2390'（ITU-R BT.2390，mpv "auto" 对 HDR 也最终解析到该曲线，显式缺省
  // 保证 HDR 兜底路径不依赖平台 auto 猜测）。可选 'auto'/'mobius'/'reinhard'/'hable'/
  // 'gamma'/'linear'/'clip'。映射到 mpv "tone-mapping" 选项。
  hdrToneMapping?: 'auto' | 'bt.2390' | 'mobius' | 'reinhard' | 'hable' | 'gamma' | 'linear' | 'clip';
  // HDR 峰值亮度检测（issue #66）：是否让 mpv 从视频信号峰值（sig-peak）动态计算
  // tone mapping 的输入峰值。'enabled' → mpv "hdr-compute-peak=yes"；'disabled' → "no"；
  // 缺省为 'auto'（mpv 在支持 compute 时启用，否则优雅降级）。映射到 mpv "hdr-compute-peak" 选项。
  hdrComputePeak?: 'auto' | 'enabled' | 'disabled';
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
  // 扩展轨道元数据（来自 mpv track-list/N/*）
  codec?: string;
  profile?: string;
  level?: number;
  bitrate?: number;
  isDefault?: boolean;
  isForced?: boolean;
  // 视频轨道特有
  resolution?: string;
  fps?: number;
  aspectRatio?: string;
  isInterlaced?: boolean;
  // 音频轨道特有
  sampleRate?: number;
  channels?: number;
  channelLayout?: string;
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
  // 扩展视频参数元数据（来自 mpv video-params/*）
  bitDepth?: number;
  colorPrimaries?: string;
  colorTransfer?: string;
  colorMatrix?: string;
  videoRange?: string;
  fps?: number;
  aspectRatio?: string;
  isInterlaced?: boolean;
  colorLevels?: string;
  videoBitrate?: number; // 实时视频码率（bps，来自 mpv video-bitrate）
}

export interface AudioParams {
  sampleRate?: number;
  channels?: number;
  channelLayout?: string;
  codec?: string;
  sampleFormat?: string;
  audioBitrate?: number; // 实时音频码率（bps，来自 mpv audio-bitrate）
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
  // 原生状态字符串。首次播放为 "playing"（SDK 转 playing 并触发 firstFrame）；
  // 恢复播放为 "resumed"（SDK 转 playing 但不重复 firstFrame）。消费方若直接处理
  // message，须同时处理 "playing" 与 "resumed"，否则恢复播放后播放态可能不更新
  // （如 _isPlaying 卡 false 导致无法暂停）。
  message?: string;
  // 当前播放位置对应的字幕纯文本（已去除 ASS/SRT 标记），来自 mpv "sub-text"
  // 属性；空字符串表示当前无字幕命中。与视频帧内是否真正合成字幕像素无关，
  // 供消费方（entry 调试页、vidall-tv 等）自行绘制字幕 UI 时使用。
  subtitleText?: string;
}

// SW 软件渲染帧数据（模拟器等无 GL 环境下的 PixelMap 回调路径）。
// data 为 RGBA 紧凑排列的 ArrayBuffer，宽高由 width/height 描述。
// 消费方可创建 PixelMap 并写入 Image 组件显示。
export interface FrameData {
  width: number;
  height: number;
  data: ArrayBuffer;
}
