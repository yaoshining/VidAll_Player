export type PlayerState = 'idle' | 'preparing' | 'playing' | 'paused' |
  'buffering' | 'completed' | 'error' | 'released';
export type PlayerTrackKind = 'audio' | 'video' | 'subtitle';
export type PlayerEventType = 'state' | 'firstFrame' | 'position' | 'buffering' | 'tracks' |
  'videoParams' | 'audioParams' | 'proxyLease' | 'streamingConfig' | 'log' | 'closed' | 'error';

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
}
