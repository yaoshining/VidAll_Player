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
