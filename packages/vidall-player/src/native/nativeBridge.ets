import { util } from '@kit.ArkTS';
import nativeSession, { NativePlayerEvent, NativeSessionResult } from 'libvidall_player_native.so';
import { MediaSource, PlayerSurface } from '../public/types';
import { PlayerFailure } from '../internal/playerFailure';

export interface DirectSmbCapability {
  available: boolean;
  evidenceId?: string;
}

export interface NativeBridgeEvent {
  type: 'state' | 'error' | 'videoParams' | 'tracks' | 'subtitleText';
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
  seekRelative(seconds: number): Promise<void>;
  seekPercent(percent: number): Promise<void>;
  setRate(rate: number): Promise<void>;
  selectTrack(kind: 'audio' | 'subtitle', trackId: number): Promise<void>;
  addExternalAudio(uri: string): Promise<void>;
  addExternalSubtitle(uri: string): Promise<void>;
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

// 将 MediaSource.headers 转换为 mpv `http-header-fields` 选项接受的逗号分隔 "Key: Value" 列表；
// 之前 headers（含 WebDAV Authorization）被计算出来后从未转发给原生层，导致鉴权头静默丢失，
// WebDAV 等需要认证的网络源会因 401/403 而无法渲染播放。
// 已知限制：mpv 该选项以英文逗号分隔字段，若 header 值本身含逗号会被误拆分；当前鉴权场景
// （Base64 Basic Authorization）不含逗号，暂不做转义处理。SMB 的 Authorization 头会在
// extractSmbCredentials() 中单独解码转发给原生层的 demuxer-lavf-o/stream-lavf-o，
// 这里对 kind='smb' 场景刻意留空 http-header-fields（原生层 Load() 也会按是否携带
// smbUsername/smbPassword 清空/跳过 HTTP 鉴权头，双重保证凭据不会误发到 HTTP 层）。
function buildHttpHeaderFieldsOption(headers: Record<string, string> | undefined): string {
  if (headers === undefined) {
    return '';
  }
  const fields: string[] = [];
  const keys = Object.keys(headers);
  for (let index = 0; index < keys.length; index++) {
    const key = keys[index];
    const value = headers[key];
    if (key.length > 0 && value !== undefined && value.length > 0) {
      fields.push(`${key}: ${value}`);
    }
  }
  return fields.join(',');
}

export interface SmbCredentials {
  username: string;
  password: string;
}

// direct smb:// 走 FFmpeg 的 demuxer-lavf-o/stream-lavf-o username=/password= 选项完成鉴权
// （libsmbclient 已静态链接进 libmpv.so），而不是 HTTP header——这与 WebDAV/HTTP(S) 的鉴权
// 通道不同。为避免在公开 API 上新增 SMB 专属凭据字段（违反 specs/002-controlled-direct-smb
// 的公开接口约束），SMB 凭据复用与 WebDAV 相同的 `headers.authorization: "Basic <base64>"`
// 机制传入，这里解码出用户名/密码后转发给原生层；解码失败或匿名共享时返回空字符串（视为匿名）。
export function extractSmbCredentials(source: MediaSource): SmbCredentials {
  const empty: SmbCredentials = { username: '', password: '' };
  if (source.kind !== 'smb' || source.headers === undefined) {
    return empty;
  }
  const keys = Object.keys(source.headers);
  let authorization: string | undefined;
  for (let index = 0; index < keys.length; index++) {
    if (keys[index].toLowerCase() === 'authorization') {
      authorization = source.headers[keys[index]];
      break;
    }
  }
  if (authorization === undefined || authorization.indexOf('Basic ') !== 0) {
    return empty;
  }
  try {
    const decodedBytes = new util.Base64Helper().decodeSync(authorization.substring('Basic '.length));
    const decoded = new util.TextDecoder('utf-8').decodeToString(decodedBytes);
    const separatorIndex = decoded.indexOf(':');
    if (separatorIndex < 0) {
      return empty;
    }
    const credentials: SmbCredentials = {
      username: decoded.substring(0, separatorIndex),
      password: decoded.substring(separatorIndex + 1)
    };
    return credentials;
  } catch (_) {
    return empty;
  }
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
    const credentials = extractSmbCredentials(source);
    return this.complete(nativeSession.load(
      this.handle, source.uri, buildHttpHeaderFieldsOption(source.headers),
      credentials.username, credentials.password));
  }

  play(): Promise<void> {
    return this.complete(nativeSession.play(this.handle));
  }

  pause(): Promise<void> {
    return this.complete(nativeSession.pause(this.handle));
  }

  stop(): Promise<void> {
    return this.complete(nativeSession.stop(this.handle));
  }

  seekRelative(seconds: number): Promise<void> {
    return this.complete(nativeSession.seekRelative(this.handle, seconds));
  }

  seekPercent(percent: number): Promise<void> {
    return this.complete(nativeSession.seekPercent(this.handle, percent));
  }

  setRate(rate: number): Promise<void> {
    return this.complete(nativeSession.setRate(this.handle, rate));
  }

  selectTrack(kind: 'audio' | 'subtitle', trackId: number): Promise<void> {
    return this.complete(nativeSession.selectTrack(this.handle, kind, trackId));
  }

  addExternalAudio(uri: string): Promise<void> {
    return this.complete(nativeSession.addExternalAudio(this.handle, uri));
  }

  addExternalSubtitle(uri: string): Promise<void> {
    return this.complete(nativeSession.addExternalSubtitle(this.handle, uri));
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

export function createNativePlayerBridge(subtitleFontsDir?: string): NativePlayerBridge {
  return new HarNativePlayerBridge(nativeSession.createSession(subtitleFontsDir ?? ''));
}
