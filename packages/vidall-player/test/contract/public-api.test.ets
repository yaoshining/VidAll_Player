// 候选 SDK 消费者契约：仅从包根目录导入公开符号。
import {
  createPlayer,
  ExternalAudio,
  ExternalSubtitle,
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
  VidAllPlayer
} from '@vidall/player';

export function compilePublicApiContract(): void {
  const options: PlayerOptions = { eventListener: (_event: PlayerEvent): void => {} };
  const player: VidAllPlayer = createPlayer(options);
  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/media.mp4',
    externalAudio: [{ uri: 'https://fixture.invalid/audio.aac', language: 'zh' }],
    externalSubtitles: [{ uri: 'https://fixture.invalid/subtitle.srt', format: 'srt' }]
  };
  const surface: PlayerSurface = { componentId: 'player', generation: 1, width: 1920, height: 1080 };
  const state: PlayerState = 'idle';
  const eventType: PlayerEventType = 'firstFrame';
  const trackKind: PlayerTrackKind = 'audio';
  const track: PlayerTrack = { id: 1, kind: trackKind, selected: false, recognitionStatus: 'recognized' };
  const subtitle: ExternalSubtitle = { uri: 'https://fixture.invalid/subtitle.srt' };
  const audio: ExternalAudio = { uri: 'https://fixture.invalid/audio.aac' };
  const error: PlayerError = { domain: 'native', code: 'FIXTURE', message: 'fixture', retryable: false, context: {} };
  const log: PlayerLog = { level: 'info', module: 'fixture', message: 'fixture' };
  const lease: ProxyLeaseStatus = { leaseId: 'fixture', state: 'released', retryable: false };
  void player.setRate(1);
  void player.mute(false);
  void player.addExternalAudio(audio);
  void [source, surface, state, eventType, track, subtitle, error, log, lease];
}
