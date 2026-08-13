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
  setPropertyString(): Promise<void> { return Promise.resolve(); }
  setAudioFilter(): Promise<void> { return Promise.resolve(); }
  setVolume(): Promise<void> { return Promise.resolve(); }
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

// 回归测试：验证原生 "hwdec-current" 属性通过 videoParams 事件上报，
// ArkTS 层正确映射为 VideoParams.hardwareDecoding 三态。
// message 编码格式："宽x高|hwdec值"（兼容旧格式 "宽x高" 无 hwdec 段时 hardwareDecoding 为 undefined）。
export async function videoParamsHardwareDecodingMappedFromNativeHwdec(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 1) 旧格式 "宽x高" — 无 hwdec 段，hardwareDecoding 应为 undefined
  bridge.emit({ type: 'videoParams', message: '1920x1080', eventEpoch: 1, sequence: 1, surfaceGeneration: 1 });
  // 2) 新格式 "宽x高|ohcodec" — 硬解激活
  bridge.emit({ type: 'videoParams', message: '1920x1080|ohcodec', eventEpoch: 1, sequence: 2, surfaceGeneration: 1 });
  // 3) 新格式 "宽x高|" — 空串=软件回退（选项为 auto 但实际软解）
  bridge.emit({ type: 'videoParams', message: '1920x1080|', eventEpoch: 1, sequence: 3, surfaceGeneration: 1 });
  // 4) 新格式 "宽x高|no" — 硬解不可用
  bridge.emit({ type: 'videoParams', message: '1920x1080|no', eventEpoch: 1, sequence: 4, surfaceGeneration: 1 });

  const vpEvents = received.filter((event: PlayerEvent) => event.type === 'videoParams');
  assert(vpEvents.length === 4,
    `Expected 4 videoParams events, got ${vpEvents.length}`);

  assert(vpEvents[0].params !== undefined && (vpEvents[0].params as Record<string, Object>).hardwareDecoding === undefined,
    'Old format without hwdec segment should leave hardwareDecoding undefined');

  assert(vpEvents[1].params !== undefined && (vpEvents[1].params as Record<string, Object>).hardwareDecoding === 'active',
    `ohcodec hwdec should map to "active", got ${(vpEvents[1].params as Record<string, Object>).hardwareDecoding}`);

  assert(vpEvents[2].params !== undefined && (vpEvents[2].params as Record<string, Object>).hardwareDecoding === 'fallback',
    `Empty hwdec (software fallback) should map to "fallback", got ${(vpEvents[2].params as Record<string, Object>).hardwareDecoding}`);

  assert(vpEvents[3].params !== undefined && (vpEvents[3].params as Record<string, Object>).hardwareDecoding === 'unavailable',
    `"no" hwdec should map to "unavailable", got ${(vpEvents[3].params as Record<string, Object>).hardwareDecoding}`);

  await player.release();
}

// T045: 验证 native bridge 上报含扩展字段的 tracks 事件后，
// playerSession 发出包含 codec/profile/level/bitrate/fps 等字段的 PlayerTrack 数组。
// 编码方案：JSON 数组（每条记录为一个对象），取代旧的 \x1e/\x1f 分隔符编码。
export async function tracksExtendedMetadataParsedFromNativeJson(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 模拟 native 上报包含扩展字段的 tracks JSON
  const tracksJson = JSON.stringify([
    {
      id: 1, type: 'audio', lang: 'eng', title: 'AAC - Stereo', selected: 1,
      codec: 'aac', profile: 'LC', level: 0, bitrate: 191000,
      default: 1, forced: 0, demux_samplerate: 44100, demux_channels: 2
    },
    {
      id: 2, type: 'sub', lang: 'chi', title: '中文字幕', selected: 0,
      codec: 'ass', profile: '', level: 0, bitrate: 0,
      default: 0, forced: 0
    }
  ]);
  bridge.emit({ type: 'tracks', message: tracksJson, eventEpoch: 1, sequence: 1, surfaceGeneration: 1 });

  const tracksEvents = received.filter((event: PlayerEvent) => event.type === 'tracks');
  assert(tracksEvents.length >= 1,
    `Expected at least 1 tracks event, got ${tracksEvents.length}`);

  const tracks = tracksEvents[tracksEvents.length - 1].tracks;
  assert(tracks !== undefined && tracks.length >= 2,
    `Expected at least 2 tracks in event, got ${tracks ? tracks.length : 'undefined'}`);

  // 查找音频轨道
  const audioTrack = tracks.find((t: Record<string, Object>) => t.kind === 'audio');
  assert(audioTrack !== undefined, 'Expected an audio track in the tracks event');
  assert((audioTrack as Record<string, Object>).codec === 'aac',
    `Expected audio codec "aac", got ${(audioTrack as Record<string, Object>).codec}`);
  assert((audioTrack as Record<string, Object>).profile === 'LC',
    `Expected audio profile "LC", got ${(audioTrack as Record<string, Object>).profile}`);
  assert((audioTrack as Record<string, Object>).bitrate === 191000,
    `Expected audio bitrate 191000, got ${(audioTrack as Record<string, Object>).bitrate}`);
  assert((audioTrack as Record<string, Object>).sampleRate === 44100,
    `Expected audio sampleRate 44100, got ${(audioTrack as Record<string, Object>).sampleRate}`);
  assert((audioTrack as Record<string, Object>).channels === 2,
    `Expected audio channels 2, got ${(audioTrack as Record<string, Object>).channels}`);

  // 查找字幕轨道
  const subTrack = tracks.find((t: Record<string, Object>) => t.kind === 'subtitle');
  assert(subTrack !== undefined, 'Expected a subtitle track in the tracks event');
  assert((subTrack as Record<string, Object>).codec === 'ass',
    `Expected subtitle codec "ass", got ${(subTrack as Record<string, Object>).codec}`);

  await player.release();
}

// T045 边界测试：旧格式 \x1e/\x1f 编码的 tracks 消息仍应兼容解析
export async function tracksLegacyDelimiterFormatStillParsed(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 旧格式：5 字段 \x1e/\x1f 编码
  const legacyMessage = '1\x1faudio\x1feng\x1fAAC Stereo\x1f1\x1e2\x1fsubtitle\x1fchi\x1f中文字幕\x1f0';
  bridge.emit({ type: 'tracks', message: legacyMessage, eventEpoch: 1, sequence: 1, surfaceGeneration: 1 });

  const tracksEvents = received.filter((event: PlayerEvent) => event.type === 'tracks');
  assert(tracksEvents.length >= 1,
    `Expected at least 1 tracks event from legacy format, got ${tracksEvents.length}`);

  const tracks = tracksEvents[tracksEvents.length - 1].tracks;
  assert(tracks !== undefined && tracks.length >= 2,
    `Expected at least 2 tracks from legacy format, got ${tracks ? tracks.length : 'undefined'}`);

  await player.release();
}

// T046: 验证 native bridge 上报含色彩参数的 videoParams 事件后，
// playerSession 发出包含 pixelFormat/bitDepth/colorPrimaries/colorTransfer/colorMatrix/videoRange 的 VideoParams。
// 编码格式扩展："宽x高|hwdec|pixfmt|bitDepth|primaries|transfer|matrix|videoRange|fps|rotation|aspectRatio|interlaced"
export async function videoParamsExtendedColorMetadataParsed(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 扩展格式：宽x高|hwdec|pixfmt|bitDepth|primaries|transfer|matrix|videoRange|fps|rotation|aspectRatio|interlaced
  bridge.emit({
    type: 'videoParams',
    message: '1920x1080|ohcodec|yuv420p|8|bt709|bt709|bt709|SDR|30|0|16:9|0',
    eventEpoch: 1, sequence: 1, surfaceGeneration: 1
  });

  const vpEvents = received.filter((event: PlayerEvent) => event.type === 'videoParams');
  assert(vpEvents.length >= 1,
    `Expected at least 1 videoParams event, got ${vpEvents.length}`);

  const params = vpEvents[vpEvents.length - 1].params as Record<string, Object>;
  assert(params !== undefined, 'Expected params in videoParams event');
  assert(params.width === 1920, `Expected width 1920, got ${params.width}`);
  assert(params.height === 1080, `Expected height 1080, got ${params.height}`);
  assert(params.hardwareDecoding === 'active', `Expected hardwareDecoding "active", got ${params.hardwareDecoding}`);
  assert(params.pixelFormat === 'yuv420p', `Expected pixelFormat "yuv420p", got ${params.pixelFormat}`);
  assert(params.bitDepth === 8, `Expected bitDepth 8, got ${params.bitDepth}`);
  assert(params.colorPrimaries === 'bt709', `Expected colorPrimaries "bt709", got ${params.colorPrimaries}`);
  assert(params.colorTransfer === 'bt709', `Expected colorTransfer "bt709", got ${params.colorTransfer}`);
  assert(params.colorMatrix === 'bt709', `Expected colorMatrix "bt709", got ${params.colorMatrix}`);
  assert(params.videoRange === 'SDR', `Expected videoRange "SDR", got ${params.videoRange}`);
  assert(params.fps === 30, `Expected fps 30, got ${params.fps}`);
  assert(params.rotation === 0, `Expected rotation 0, got ${params.rotation}`);
  assert(params.aspectRatio === '16:9', `Expected aspectRatio "16:9", got ${params.aspectRatio}`);
  assert(params.isInterlaced === false, `Expected isInterlaced false, got ${params.isInterlaced}`);

  await player.release();
}

// T046 边界测试：旧格式 "宽x高" 和 "宽x高|hwdec" 仍应兼容
export async function videoParamsLegacyFormatStillParsed(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 旧格式1：只有宽x高
  bridge.emit({ type: 'videoParams', message: '1920x1080', eventEpoch: 1, sequence: 1, surfaceGeneration: 1 });
  // 旧格式2：宽x高|hwdec
  bridge.emit({ type: 'videoParams', message: '1920x1080|ohcodec', eventEpoch: 1, sequence: 2, surfaceGeneration: 1 });

  const vpEvents = received.filter((event: PlayerEvent) => event.type === 'videoParams');
  assert(vpEvents.length >= 2,
    `Expected at least 2 videoParams events, got ${vpEvents.length}`);

  const params0 = vpEvents[0].params as Record<string, Object>;
  assert(params0.bitDepth === undefined,
    `Old format should leave bitDepth undefined, got ${params0.bitDepth}`);

  const params1 = vpEvents[1].params as Record<string, Object>;
  assert(params1.hardwareDecoding === 'active',
    `Old format with hwdec should still parse hardwareDecoding, got ${params1.hardwareDecoding}`);
  assert(params1.bitDepth === undefined,
    `Old format should leave bitDepth undefined, got ${params1.bitDepth}`);

  await player.release();
}

// T046 边界测试：扩展字段缺失时为 undefined，不全的扩展格式也能正确解析
export async function videoParamsPartialExtensionFieldsParsed(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 只有部分扩展字段：宽x高|hwdec|pixfmt|bitDepth（后面的字段缺失）
  bridge.emit({
    type: 'videoParams',
    message: '1920x1080|ohcodec|yuv420p|10',
    eventEpoch: 1, sequence: 1, surfaceGeneration: 1
  });

  const vpEvents = received.filter((event: PlayerEvent) => event.type === 'videoParams');
  assert(vpEvents.length >= 1,
    `Expected at least 1 videoParams event, got ${vpEvents.length}`);

  const params = vpEvents[vpEvents.length - 1].params as Record<string, Object>;
  assert(params.pixelFormat === 'yuv420p', `Expected pixelFormat "yuv420p", got ${params.pixelFormat}`);
  assert(params.bitDepth === 10, `Expected bitDepth 10, got ${params.bitDepth}`);
  assert(params.colorPrimaries === undefined,
    `Expected colorPrimaries undefined for partial message, got ${params.colorPrimaries}`);
  assert(params.videoRange === undefined,
    `Expected videoRange undefined for partial message, got ${params.videoRange}`);

  await player.release();
}

// 回归测试：验证原生 mpv "time-pos" / "duration" 属性变化能正确转译为公开
// 'position' 事件，携带 positionMs / durationMs（毫秒，与 VidAll_TV 的 IPlayer
// onTimeUpdate 契约对齐），并遵循与其它原生事件一致的 epoch/generation 门控。
// 这条通道之前缺失，导致 VidAll_TV 进度条与续播逻辑拿不到时间更新。
export async function nativePositionEventUpdatesPublicPosition(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // mpv time-pos / duration 均为秒，C++ 侧 ×1000 转毫秒后以 JSON 编码上报。
  bridge.emit({
    type: 'position',
    message: '{"positionMs":1234,"durationMs":56789}',
    eventEpoch: 1, sequence: 1, surfaceGeneration: 1
  });
  // 陈旧 epoch / generation 的 position 事件必须被丢弃，不得污染公开事件流。
  bridge.emit({
    type: 'position',
    message: '{"positionMs":9999,"durationMs":9999}',
    eventEpoch: 0, sequence: 2, surfaceGeneration: 1
  });
  bridge.emit({
    type: 'position',
    message: '{"positionMs":9999,"durationMs":9999}',
    eventEpoch: 1, sequence: 2, surfaceGeneration: 2
  });
  // 非法 JSON / 空 message 不得崩溃，也不得产生公开事件。
  bridge.emit({ type: 'position', message: '', eventEpoch: 1, sequence: 3, surfaceGeneration: 1 });
  bridge.emit({ type: 'position', message: 'not-json', eventEpoch: 1, sequence: 4, surfaceGeneration: 1 });

  const posEvents = received.filter((event: PlayerEvent) => event.type === 'position');
  assert(posEvents.length === 1,
    `Expected exactly 1 accepted position event, got ${posEvents.length}`);
  assert(posEvents[0].positionMs === 1234,
    `Expected positionMs 1234, got ${posEvents[0].positionMs}`);
  assert(posEvents[0].durationMs === 56789,
    `Expected durationMs 56789, got ${posEvents[0].durationMs}`);

  await player.release();
}

// 节流回归测试：mpv time-pos 默认每帧上报，ArkTS 侧必须保证两次公开
// 'position' emit 间隔 ≥ 100ms（与 VidAll_TV IjkPlayerAdapter 100ms 轮询节奏
// 对齐），避免事件洪泛冲垮订阅方。同一 100ms 窗口内的连续事件只放行一个。
export async function nativePositionEventThrottlesAt100ms(): Promise<void> {
  const bridge = new RecordingNativeBridge();
  const player = new PlayerSession(undefined, bridge);
  const received: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent): void => { received.push(event); });

  await player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 });
  await player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' });

  // 同一 100ms 窗口内连发 5 个递增 position 事件（模拟 mpv 高频上报），
  // 节流后只应放行首个命中（positionMs=1000），其余在窗口内被抑制。
  let seq = 1;
  for (let i = 0; i < 5; i++) {
    bridge.emit({
      type: 'position',
      message: `{"positionMs":${1000 + i},"durationMs":60000}`,
      eventEpoch: 1, sequence: seq, surfaceGeneration: 1
    });
    seq += 1;
  }

  let posEvents = received.filter((event: PlayerEvent) => event.type === 'position');
  assert(posEvents.length === 1,
    `Expected exactly 1 position event within 100ms window, got ${posEvents.length}`);
  assert(posEvents[0].positionMs === 1000,
    `Expected first-accepted positionMs 1000, got ${posEvents[0].positionMs}`);

  // 节流窗口结束后（>100ms），新的 position 事件必须再次放行——否则实现可能在
  // 首次 emit 后永久抑制后续事件，而上面的断言无法发现该缺陷。
  await new Promise<void>((resolve) => setTimeout(resolve, 120));
  bridge.emit({
    type: 'position',
    message: '{"positionMs":2000,"durationMs":60000}',
    eventEpoch: 1, sequence: seq, surfaceGeneration: 1
  });
  seq += 1;

  posEvents = received.filter((event: PlayerEvent) => event.type === 'position');
  assert(posEvents.length === 2,
    `Expected 2nd position event after throttle window, got ${posEvents.length}`);
  assert(posEvents[1].positionMs === 2000,
    `Expected post-window positionMs 2000, got ${posEvents[1].positionMs}`);

  await player.release();
}
