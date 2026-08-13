import { MediaSource, PlayerError, VidAllPlayer } from '@vidall/player';
import { PlayerSession } from '../../src/internal/playerSession';
import { DirectSmbCapability, NativeBridgeEvent, NativePlayerBridge } from '../../src/native/nativeBridge';

class LifecycleNativeBridge implements NativePlayerBridge {
  private released: boolean = false;
  private surfaceGeneration?: number;
  private eventEpoch: number = 0;
  private listener?: (event: NativeBridgeEvent) => void;
  readonly properties: string[] = [];

  getDirectSmbCapability(): Promise<DirectSmbCapability> { return Promise.resolve({ available: false }); }
  attachSurface(surface: { generation: number }): Promise<void> {
    this.surfaceGeneration = surface.generation;
    return Promise.resolve();
  }
  resizeSurface(surface: { generation: number }): Promise<void> {
    this.surfaceGeneration = surface.generation;
    return Promise.resolve();
  }
  detachSurface(): Promise<void> { this.surfaceGeneration = undefined; return Promise.resolve(); }
  load(): Promise<void> {
    this.eventEpoch++;
    if (this.surfaceGeneration === undefined) {
      return Promise.reject(this.failure('SURFACE_UNAVAILABLE'));
    }
    this.listener?.({
      type: 'state', message: 'preparing', eventEpoch: this.eventEpoch, sequence: 1,
      surfaceGeneration: this.surfaceGeneration
    });
    return Promise.resolve();
  }
  play(): Promise<void> { return Promise.resolve(); }
  pause(): Promise<void> { return Promise.reject(this.failure('FEATURE_UNSUPPORTED')); }
  setPropertyString(property: string, value: string): Promise<void> {
    this.properties.push(`${property}=${value}`);
    return Promise.resolve();
  }
  stop(): Promise<void> { return Promise.resolve(); }
  seekRelative(): Promise<void> { return Promise.resolve(); }
  seekPercent(): Promise<void> { return Promise.resolve(); }
  setRate(): Promise<void> { return Promise.resolve(); }
  selectTrack(): Promise<void> { return Promise.resolve(); }
  addExternalAudio(): Promise<void> { return Promise.resolve(); }
  addExternalSubtitle(): Promise<void> { return Promise.resolve(); }
  getFrameData(): null { return null; }
  release(): Promise<void> { this.released = true; return Promise.resolve(); }
  subscribe(listener: (event: NativeBridgeEvent) => void): () => void {
    this.listener = listener;
    return (): void => { this.listener = undefined; };
  }

  private failure(code: string): Error & { playerError: PlayerError } {
    const error = new Error(code) as Error & { playerError: PlayerError };
    error.playerError = { domain: 'native', code, message: code, retryable: false, context: {} };
    return error;
  }
}

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

async function expectFailure(operation: () => Promise<void>, code: string): Promise<void> {
  let failure: (Error & { playerError?: PlayerError }) | undefined = undefined;
  try {
    await operation();
  } catch (error) {
    failure = error as Error & { playerError?: PlayerError };
  }
  assert(failure?.playerError?.code === code, `Expected ${code}.`);
}

export async function playerLifecycleMaintainsTypedFailuresAndNewSessionRecovery(): Promise<void> {
  const nativeBridge = new LifecycleNativeBridge();
  const player: VidAllPlayer = new PlayerSession(undefined, nativeBridge);
  await expectFailure(() => player.load({ kind: 'https', uri: '' }), 'INVALID_MEDIA_SOURCE');
  await expectFailure(() => player.play(), 'INVALID_STATE');
  await expectFailure(() => player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' }), 'SURFACE_UNAVAILABLE');

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  const source: MediaSource = { kind: 'https', uri: 'https://fixture.invalid/media.mp4' };
  await player.load(source);
  await player.setPropertyString('sid', '2');
  await player.setPropertyString('sub-visibility', 'yes');
  assert(nativeBridge.properties.join(',') === 'sid=2,sub-visibility=yes',
    'String properties must be forwarded through the serialized native bridge.');
  await expectFailure(() => player.setPropertyString('', 'yes'), 'INPUT_INVALID');
  await player.stop();
  await player.stop();
  await player.release();
  await player.release();
  await expectFailure(() => player.load(source), 'RELEASED');
  await expectFailure(() => player.play(), 'RELEASED');
  await expectFailure(() => player.setPropertyString('sid', 'no'), 'RELEASED');

  const recovered: VidAllPlayer = new PlayerSession(undefined, new LifecycleNativeBridge());
  await recovered.attachSurface({ componentId: 'recovered', generation: 1, width: 1920, height: 1080 });
  await recovered.load(source);
  await recovered.release();
}
