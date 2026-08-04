import { PlayerEvent } from '@vidall/player';
import { PlayerSession } from '../../src/internal/playerSession';
import { DirectSmbCapability, NativeBridgeEvent, NativePlayerBridge } from '../../src/native/nativeBridge';

class RecordingNativeBridge implements NativePlayerBridge {
  private readonly listeners: Array<(event: NativeBridgeEvent) => void> = [];
  private released: boolean = false;

  getDirectSmbCapability(): Promise<DirectSmbCapability> { return Promise.resolve({ available: false }); }
  attachSurface(): Promise<void> { return Promise.resolve(); }
  resizeSurface(): Promise<void> { return Promise.resolve(); }
  detachSurface(): Promise<void> { return Promise.resolve(); }
  load(): Promise<void> { return Promise.resolve(); }
  play(): Promise<void> { return Promise.resolve(); }
  pause(): Promise<void> { return Promise.resolve(); }
  stop(): Promise<void> { return Promise.resolve(); }

  release(): Promise<void> {
    this.released = true;
    this.listeners.splice(0, this.listeners.length);
    return Promise.resolve();
  }

  subscribe(listener: (event: NativeBridgeEvent) => void): () => void {
    this.listeners.push(listener);
    return (): void => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) {
        this.listeners.splice(index, 1);
      }
    };
  }

  emit(event: NativeBridgeEvent): void {
    if (this.released) {
      return;
    }
    const listeners = this.listeners.slice();
    for (let index = 0; index < listeners.length; index++) {
      listeners[index](event);
    }
  }
}

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

export async function nativeEventsRejectStaleContextAndReleaseDelivery(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });
  bridge.emit({ type: 'state', message: 'preparing', eventEpoch: 0, sequence: 1, surfaceGeneration: 1 });
  bridge.emit({ type: 'state', message: 'preparing', eventEpoch: 1, sequence: 2, surfaceGeneration: 2 });
  bridge.emit({ type: 'state', message: 'preparing', eventEpoch: 1, sequence: 2, surfaceGeneration: 1 });
  bridge.emit({ type: 'state', message: 'preparing', eventEpoch: 1, sequence: 3, surfaceGeneration: 1 });

  assert(received.filter((event: PlayerEvent) => event.type === 'state' && event.state === 'preparing').length === 1,
    'Only the current epoch, generation, and in-order native event may update public state.');

  await player.release();
  const beforeLateEvent = received.length;
  bridge.emit({ type: 'error', message: 'sensitive://media/path', eventEpoch: 1, sequence: 4, surfaceGeneration: 1 });
  assert(received.length === beforeLateEvent, 'Release must prevent native bridge events from reaching subscribers.');
}

// 回归测试：验证原生 "sub-text" 属性变化（mpv 解析出的当前字幕纯文本）能正确
// 转译为公开 subtitleText 事件，且遵循与其它原生事件一致的 epoch/generation 门控。
// 这条通道独立于软件渲染合成管线是否把字幕像素画进视频帧，用于让消费方
// （entry 调试页、vidall-tv 等）自行绘制字幕 UI、验证字幕解析是否生效。
export async function nativeSubtitleTextEventUpdatesPublicSubtitleText(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  bridge.emit({ type: 'subtitleText', message: 'Hello World Subtitle Test', eventEpoch: 1, sequence: 1, surfaceGeneration: 1 });
  // 陈旧 epoch/generation 的字幕事件必须被丢弃，不得污染公开事件流。
  bridge.emit({ type: 'subtitleText', message: 'stale epoch text', eventEpoch: 0, sequence: 2, surfaceGeneration: 1 });
  bridge.emit({ type: 'subtitleText', message: 'stale generation text', eventEpoch: 1, sequence: 2, surfaceGeneration: 2 });
  // 空字符串代表"当前无字幕命中"，必须原样透传，不能被当作无效值丢弃。
  bridge.emit({ type: 'subtitleText', message: '', eventEpoch: 1, sequence: 2, surfaceGeneration: 1 });

  const subtitleEvents = received.filter((event: PlayerEvent) => event.type === 'subtitleText');
  assert(subtitleEvents.length === 2,
    `Expected exactly 2 accepted subtitleText events, got ${subtitleEvents.length}`);
  assert(subtitleEvents[0].subtitleText === 'Hello World Subtitle Test',
    `Expected first subtitleText to carry native text, got ${subtitleEvents[0].subtitleText}`);
  assert(subtitleEvents[1].subtitleText === '',
    'Empty subtitleText (no active cue) must be forwarded, not dropped.');

  await player.release();
}
