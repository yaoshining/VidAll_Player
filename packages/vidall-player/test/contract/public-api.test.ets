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
  VidAllPlayer,
  VidAllPlayerSurfaceTarget,
  XComponentSurfaceAdapter
} from '@vidall/player';

interface PlayerFailureLike {
  playerError?: PlayerError;
}

function expectRejected(operation: () => Promise<void>, code: string): Promise<void> {
  return operation().then(() => {
    throw new Error(`Expected ${code}.`);
  }).catch((error: PlayerFailureLike) => {
    if (error.playerError?.code !== code) {
      throw new Error(`Expected ${code}.`);
    }
  });
}

export async function publicPlayerReleaseContract(): Promise<void> {
  const player: VidAllPlayer = createPlayer();
  await player.release();
  await player.release();
  await expectRejected(() => player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' }), 'RELEASED');
  await expectRejected(() => player.play(), 'RELEASED');
  await expectRejected(() => player.attachSurface({ componentId: 'player', generation: 1, width: 1920, height: 1080 }), 'RELEASED');
  await expectRejected(() => player.resizeSurface({ componentId: 'player', generation: 1, width: 1920, height: 1080 }), 'RELEASED');
  await expectRejected(() => player.detachSurface(1), 'RELEASED');
}

export function compilePublicApiContract(): void {
  const options: PlayerOptions = { eventListener: (_event: PlayerEvent): void => {} };
  const player: VidAllPlayer = createPlayer(options);
  // 硬件解码开关：'auto'（默认，优先 OHOS ohcodec 硬解、失败回退软解）或 'disabled'（纯软解）
  const hwdecAuto: VidAllPlayer = createPlayer({ hardwareDecoding: 'auto' });
  const hwdecDisabled: VidAllPlayer = createPlayer({ hardwareDecoding: 'disabled' });
  const adapter: XComponentSurfaceAdapter = new XComponentSurfaceAdapter(new VidAllPlayerSurfaceTarget(player));
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
  const lease: ProxyLeaseStatus = { leaseId: 'fixture', state: 'released', epoch: 1, retryable: false };
  void player.setRate(1);
  void player.mute(false);
  void player.addExternalAudio(audio);
  void [adapter, source, surface, state, eventType, track, subtitle, error, log, lease, hwdecAuto, hwdecDisabled];
}
