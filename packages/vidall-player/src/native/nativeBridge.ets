import nativeSession, { NativePlayerEvent, NativeSessionResult } from 'libvidall_player_native.so';
import { MediaSource, PlayerSurface } from '../public/types';
import { PlayerFailure } from '../internal/playerFailure';

export interface DirectSmbCapability {
  available: boolean;
  evidenceId?: string;
}

export interface NativeBridgeEvent {
  type: 'state' | 'error';
  message: string;
  eventEpoch: number;
  sequence: number;
  surfaceGeneration: number;
}

// Internal-only contract. System handles stay inside the native implementation.
export interface NativePlayerBridge {
  getDirectSmbCapability(): Promise<DirectSmbCapability>;
  attachSurface(surface: PlayerSurface): Promise<void>;
  resizeSurface(surface: PlayerSurface): Promise<void>;
  detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  stop(): Promise<void>;
  release(): Promise<void>;
  subscribe(listener: (event: NativeBridgeEvent) => void): () => void;
}

function nativeFailure(result: NativeSessionResult): PlayerFailure {
  const renderFailure = result.code === 'SURFACE_UNAVAILABLE';
  const inputFailure = result.code === 'INPUT_INVALID';
  const released = result.code === 'RELEASED';
  return new PlayerFailure({
    domain: renderFailure ? 'render' : (inputFailure ? 'input' : (released ? 'lifecycle' : 'native')),
    code: result.code,
    message: renderFailure ? '当前没有可用的 XComponent 画面。' :
      (inputFailure ? '原生播放器参数无效。' :
        (released ? '播放器会话已释放。' : 'libmpv 原生操作失败。')),
    retryable: false,
    context: {}
  });
}

class HarNativePlayerBridge implements NativePlayerBridge {
  private readonly handle: number;
  private released: boolean = false;
  private readonly listeners: Array<(event: NativeBridgeEvent) => void> = [];

  constructor(result: NativeSessionResult) {
    if (!result.ok || result.handle <= 0) {
      throw nativeFailure(result);
    }
    this.handle = result.handle;
    this.requireResult(nativeSession.setEventCallback(this.handle, (event: NativePlayerEvent): void => {
      if (this.released) {
        return;
      }
      const listeners = this.listeners.slice();
      for (let index = 0; index < listeners.length; index++) {
        listeners[index](event);
      }
    }));
  }

  getDirectSmbCapability(): Promise<DirectSmbCapability> {
    const capability: DirectSmbCapability = { available: false };
    return Promise.resolve(capability);
  }

  attachSurface(surface: PlayerSurface): Promise<void> {
    return this.complete(nativeSession.attachSurface(this.handle, surface.componentId, surface.generation, surface.width, surface.height));
  }

  resizeSurface(surface: PlayerSurface): Promise<void> {
    return this.complete(nativeSession.resizeSurface(this.handle, surface.componentId, surface.generation, surface.width, surface.height));
  }

  detachSurface(generation: number): Promise<void> {
    return this.complete(nativeSession.detachSurface(this.handle, generation));
  }

  load(source: MediaSource): Promise<void> {
    return this.complete(nativeSession.load(this.handle, source.uri));
  }

  play(): Promise<void> {
    return this.complete(nativeSession.play(this.handle));
  }

  pause(): Promise<void> {
    return Promise.reject(new PlayerFailure({ domain: 'native', code: 'FEATURE_UNSUPPORTED', message: '暂停尚未由最小 libmpv bridge 提供。', retryable: false, context: {} }));
  }

  stop(): Promise<void> {
    return this.complete(nativeSession.stop(this.handle));
  }

  release(): Promise<void> {
    if (this.released) {
      return Promise.resolve();
    }
    const result: NativeSessionResult = nativeSession.releaseSession(this.handle);
    if (!result.ok && result.code !== 'ALREADY_RELEASED') {
      return Promise.reject(nativeFailure(result));
    }
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

  private complete(result: NativeSessionResult): Promise<void> {
    if (this.released) {
      return Promise.reject(nativeFailure({ ok: false, handle: this.handle, code: 'RELEASED' }));
    }
    if (!result.ok) {
      return Promise.reject(nativeFailure(result));
    }
    return Promise.resolve();
  }

  private requireResult(result: NativeSessionResult): void {
    if (!result.ok) {
      throw nativeFailure(result);
    }
  }
}

export function createNativePlayerBridge(): NativePlayerBridge {
  return new HarNativePlayerBridge(nativeSession.createSession());
}
