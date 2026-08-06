// 此文件是候选 SDK 的唯一消费者入口；内部桥接与原生实现不属于公开 API。
export { createPlayer, VidAllPlayer } from './src/public/player';
export { XComponentSurfaceAdapter, VidAllPlayerSurfaceTarget } from './src/xcomponent/surfaceAdapter';
export {
  AudioParams,
  ExternalAudio,
  ExternalSubtitle,
  FrameData,
  MediaSource,
  PlayerError,
  PlayerEvent,
  PlayerEventType,
  PlayerLog,
  PlayerOptions,
  PlayerState,
  PlayerSurface,
  PlayerTrack,
  PlayerTrackKind,
  ProxyLeaseStatus,
  VideoParams
} from './src/public/types';
