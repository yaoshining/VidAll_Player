# ArkTS SDK 契约

包名暂定为 `@vidall/player`，最终名称须经批准私有 ohpm 源登记后冻结。只导出下列 ArkTS 类型和 `createPlayer`；不导出 NAPI、NativeWindow、EGL/GLES 或 libmpv 句柄。

```ts
export type PlayerState = 'idle' | 'preparing' | 'playing' | 'paused' |
  'buffering' | 'completed' | 'error' | 'released';
export interface PlayerSurface { componentId: string; generation: number; width: number; height: number; }
export interface PlayerOptions { eventListener?: (event: PlayerEvent) => void; }
export interface MediaSource {
  kind: 'localFile' | 'http' | 'https' | 'hls' | 'dash' | 'localhostProxy';
  uri: string; headers?: Record<string, string>; externalSubtitles?: ExternalSubtitle[]; proxyLeaseId?: string;
}
export interface ExternalSubtitle { uri: string; title?: string; format?: 'srt' | 'ass' | 'ssa' | 'webvtt' | 'pgs' | 'vobsub'; }
export interface PlayerTrack { id: number; kind: 'audio' | 'video' | 'subtitle'; language?: string; title?: string; selected: boolean; recognitionStatus: 'recognized' | 'renderable' | 'degraded' | 'unsupported'; }
export interface PlayerError { domain: 'input' | 'network' | 'security' | 'media' | 'render' | 'native' | 'lifecycle'; code: string; message: string; retryable: boolean; context: Record<string, string | number | boolean>; }
export type PlayerEvent = { type: 'state'; sequence: number; state: PlayerState } | { type: 'position'; sequence: number; positionMs: number; durationMs?: number; percent?: number } | { type: 'buffering'; sequence: number; paused: boolean; percent?: number } | { type: 'tracks'; sequence: number; tracks: PlayerTrack[] } | { type: 'videoParams' | 'audioParams' | 'log' | 'closed'; sequence: number } | { type: 'error'; sequence: number; error: PlayerError };
export interface VidAllPlayer {
  attachSurface(surface: PlayerSurface): Promise<void>; resizeSurface(surface: PlayerSurface): Promise<void>; detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>; play(): Promise<void>; pause(): Promise<void>; seekRelative(seconds: number): Promise<void>; seekPercent(percent: number): Promise<void>;
  setSpeed(speed: number): Promise<void>; setVolume(volume: number): Promise<void>; setMuted(muted: boolean): Promise<void>;
  selectTrack(kind: PlayerTrack['kind'], id: number | null): Promise<void>; addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void>; setSubtitleDelay(delayMs: number): Promise<void>;
  subscribe(listener: (event: PlayerEvent) => void): () => void; stop(): Promise<void>; release(): Promise<void>;
}
export function createPlayer(options?: PlayerOptions): VidAllPlayer;
```

| 命令 | 前置条件 | 幂等/失败规则 |
|---|---|---|
| `attachSurface` / `resizeSurface` | 尺寸大于零、世代有效 | 同世代同尺寸可无操作；释放后拒绝 `SESSION_RELEASED`。 |
| `detachSurface` | 可为已销毁世代 | 旧/重复世代无操作，不得销毁新世代。 |
| `load` | URI/头部校验通过 | 串行切源；失败进入 `error`，仍可加载下一条。 |
| 控制命令 | 会话未释放 | 状态不满足时拒绝 `INVALID_STATE`，不隐式建实例。 |
| `release` | 任意状态 | 可重复；首次释放停止事件和原生资源，后续无操作。 |

## 线程与版本语义

- ArkTS 调用只进入每会话串行命令队列；媒体解析、网络等待、libmpv 事件处理和 EGL/GLES 渲染不得阻塞 ArkUI UI 线程。
- `PlayerSurface.componentId` 仅标识 ArkTS XComponent 适配对象，不能是 NativeWindow、指针或可跨线程的原生句柄；`generation` 必须由 XComponent 每次重新附着递增。
- 每个 `PlayerEvent.sequence` 在单一会话内严格递增；在 `closed` 事件后或会话释放后不得再投递事件。消费者不得将不同会话的序号相互比较。
- API 15 为安装兼容下限、API 19 为新增/敏感 API 审查点、API 22 为认证目标。仅高版本可用能力必须运行时探测，并将 API 15--18 的拒绝、无操作或软件降级记录到能力证据。

认证头只在运行时内存传递；重定向只在受信任范围内传递认证头；所有日志、事件和错误脱敏。当前包名和 API 仅为候选契约；正式发布前需在批准私有 ohpm 源登记后冻结语义版本和包名。
