export type PlayerState = 'idle' | 'preparing' | 'playing' | 'paused' |
  'buffering' | 'completed' | 'error' | 'released';
export type PlayerTrackKind = 'audio' | 'video' | 'subtitle';
export type PlayerEventType = 'state' | 'position' | 'buffering' | 'tracks' |
  'videoParams' | 'audioParams' | 'log' | 'closed' | 'error';

export interface PlayerSurface {
  componentId: string;
  generation: number;
  width: number;
  height: number;
}

export interface PlayerOptions { eventListener?: (event: PlayerEvent) => void; }

export interface MediaSource {
  kind: 'localFile' | 'http' | 'https' | 'hls' | 'dash' | 'localhostProxy';
  uri: string;
  headers?: Record<string, string>;
  externalSubtitles?: ExternalSubtitle[];
  proxyLeaseId?: string;
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

export interface PlayerEvent {
  type: PlayerEventType;
  sequence: number;
  state?: PlayerState;
  positionMs?: number;
  durationMs?: number;
  percent?: number;
  paused?: boolean;
  tracks?: PlayerTrack[];
  error?: PlayerError;
  // 仅用于 log 事件的脱敏文本载荷（如 SMB 代理租约释放记录）。
  message?: string;
}
