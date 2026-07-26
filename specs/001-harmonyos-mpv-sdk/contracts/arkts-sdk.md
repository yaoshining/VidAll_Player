# ArkTS SDK 契约

包名暂定为 `@vidall/player`，最终名称须经批准私有 ohpm 源登记后冻结。只导出下列 ArkTS 类型和 `createPlayer`；不导出 NAPI、NativeWindow、EGL/GLES 或 libmpv 句柄。

```ts
export type PlayerState = 'idle' | 'preparing' | 'playing' | 'paused' |
  'buffering' | 'completed' | 'error' | 'released';
export interface PlayerSurface { componentId: string; generation: number; width: number; height: number; }
export interface PlayerOptions { eventListener?: (event: PlayerEvent) => void; }
export interface MediaSource {
  kind: 'localFile' | 'http' | 'https' | 'hls' | 'dash' | 'localhostProxy';
  uri: string; headers?: Record<string, string>; externalAudio?: ExternalAudio[]; externalSubtitles?: ExternalSubtitle[]; proxyLeaseId?: string;
}
export interface ExternalSubtitle { uri: string; title?: string; format?: 'srt' | 'ass' | 'ssa' | 'webvtt' | 'pgs' | 'vobsub'; }
export interface ExternalAudio { uri: string; title?: string; language?: string; }
export interface PlayerTrack { id: number; kind: 'audio' | 'video' | 'subtitle'; language?: string; title?: string; selected: boolean; recognitionStatus: 'recognized' | 'renderable' | 'degraded' | 'unsupported'; }
export interface PlayerError { domain: 'input' | 'network' | 'security' | 'media' | 'render' | 'native' | 'lifecycle'; code: string; message: string; retryable: boolean; context: Record<string, string | number | boolean>; }
export interface VideoParams { width: number; height: number; pixelFormat?: string; rotation?: number; decoder?: string; hardwareDecoding?: 'active' | 'fallback' | 'unavailable'; }
export interface AudioParams { sampleRate?: number; channels?: number; channelLayout?: string; codec?: string; }
export interface PlayerLog { level: 'debug' | 'info' | 'warn' | 'error'; module: string; message: string; }
export interface ProxyLeaseStatus { leaseId: string; state: 'acquired' | 'renewed' | 'releaseRequested' | 'released' | 'expired' | 'cleanupFailed'; retryable: boolean; }
export interface PlayerEventBase { sequence: number; eventEpoch: number; surfaceGeneration?: number; }
export type PlayerEvent = PlayerEventBase & (
  | { type: 'state'; state: PlayerState }
  | { type: 'firstFrame'; surfaceGeneration: number; positionMs?: number }
  | { type: 'position'; positionMs: number; durationMs?: number; percent?: number }
  | { type: 'buffering'; paused: boolean; percent?: number; cacheDurationMs?: number }
  | { type: 'tracks'; tracks: PlayerTrack[] }
  | { type: 'videoParams'; params: VideoParams }
  | { type: 'audioParams'; params: AudioParams }
  | { type: 'proxyLease'; lease: ProxyLeaseStatus }
  | { type: 'log'; log: PlayerLog }
  | { type: 'closed' }
  | { type: 'error'; error: PlayerError });
export interface VidAllPlayer {
  attachSurface(surface: PlayerSurface): Promise<void>; resizeSurface(surface: PlayerSurface): Promise<void>; detachSurface(generation: number): Promise<void>;
  load(source: MediaSource): Promise<void>; play(): Promise<void>; pause(): Promise<void>; seekRelative(seconds: number): Promise<void>; seekPercent(percent: number): Promise<void>;
  setRate(rate: number): Promise<void>; setVolume(volume: number): Promise<void>; mute(muted: boolean): Promise<void>;
  selectTrack(kind: PlayerTrack['kind'], id: number | null): Promise<void>; addExternalAudio(audio: ExternalAudio): Promise<void>; addExternalSubtitle(subtitle: ExternalSubtitle): Promise<void>; setSubtitleDelay(delayMs: number): Promise<void>;
  subscribe(listener: (event: PlayerEvent) => void): () => void; stop(): Promise<void>; release(): Promise<void>;
}
export function createPlayer(options?: PlayerOptions): VidAllPlayer;
```

| 命令 | 前置条件 | 幂等/失败规则 |
|---|---|---|
| `attachSurface` / `resizeSurface` | 尺寸大于零、世代有效 | 同世代同尺寸可无操作；只确认内部原生层已接受操作，不代表首帧；释放后拒绝 `SESSION_RELEASED`。 |
| `detachSurface` | 可为已销毁世代 | 旧/重复世代无操作，不得销毁新世代；旧 generation 的渲染/事件必须丢弃。 |
| `load` | URI/头部校验通过 | 串行切源；成功只代表原生层已接受加载，真实状态、轨道与首帧由原生事件确认；失败进入 `error`，仍可加载下一条。 |
| 控制命令 | 会话未释放 | `play`、暂停、跳转、`setRate`、音量、静音、轨道、外挂音频和字幕命令均须经内部原生桥接确认；状态不满足时拒绝 `INVALID_STATE`，不隐式建实例。 |
| `release` | 任意状态 | 可重复；首次释放建立回调屏障、释放原生资源并至多投递一个 `closed`，Promise 完成后绝不再回调。 |

## 真实事件、线程与版本语义

- 状态、位置、缓冲、轨道、音视频参数、日志、关闭和错误只可由 libmpv、渲染器或内部桥接生命周期产生。ArkTS 不得因 `load()`、`play()` 或 Promise 成功伪造 `preparing`、`playing`、轨道或首帧。
- `firstFrame` 仅表示当前 `surfaceGeneration` 的渲染器已提交真实画面；`file-loaded`、解码器创建、`load()` 或 `play()` 成功均不等价于首帧。
- ArkTS 调用只进入每会话串行命令队列；媒体解析、网络等待、libmpv 事件处理和 EGL/GLES 渲染不得阻塞 ArkUI UI 线程。
- `PlayerSurface.componentId` 仅标识 ArkTS XComponent 适配对象，不能是 NativeWindow、指针或可跨线程的原生句柄；`generation` 必须由 XComponent 每次重新附着递增。SDK 内部独占 NativeWindow 和渲染资源。
- 每个 `PlayerEvent.sequence` 在单一会话内严格递增。`eventEpoch` 在原生会话重建或媒体源切换时递增；实现必须先按 epoch、再按 surface generation 丢弃陈旧事件。消费者不得将不同会话的序号相互比较。
- API 15 为安装兼容下限、API 19 为新增/敏感 API 审查点、API 22 为认证目标。仅高版本可用能力必须运行时探测，并将 API 15--18 的拒绝、无操作或软件降级记录到能力证据。

## 网络与 SMB lease

- URI 禁止 userinfo。认证头仅在运行时内存传递，并且只能发送给初始 URI 所属的明确受信任范围；跨主机、跨端口、降级协议或未确认范围的重定向必须剥离认证头并产生脱敏的可消费错误。
- `localhostProxy` 仅允许 loopback plain HTTP URI。`proxyLeaseId` 是业务层已启动代理的匿名 lease 标识；SDK 只消费、关联并在切源、失败、stop 或 release 时请求释放，不实现 SMB、代理启动、协议恢复或解码之外的业务逻辑。
- lease 协作通过 `proxyLease` 事件向消费者公开 `acquired`、`renewed`、`releaseRequested`、`released`、`expired` 和 `cleanupFailed` 结果；业务层以提供给 `MediaSource` 的 lease 标识关联其代理协议。无法续期、代理不可用或未确认释放必须产生结构化错误/脱敏日志，并记录到候选证据；消费者不直接调用私有 NAPI。

当前包名和 API 仅为候选契约；正式发布前需在批准私有 ohpm 源登记后冻结语义版本和包名。内部 wire schema、线程所有权和释放屏障见 [`native-bridge.md`](./native-bridge.md)。
