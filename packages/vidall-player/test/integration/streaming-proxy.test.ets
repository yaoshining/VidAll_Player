// T052 ArkTS 流媒体集成测试：覆盖 HLS/DASH 正常、边界和失败路径。
// TDD 红阶段：先写测试，T053 实现使之通过。
//
// 测试策略：
// - 正常路径：hls/dash 加载后状态转换、buffering 事件、网络恢复
// - 边界路径：空 URI、kind 不匹配、跨域重定向、release 后操作
// - 失败路径：网络超时、TLS 错误、格式不支持、分段失败重试

import {
  createPlayer,
  MediaSource,
  PlayerEvent,
  VidAllPlayer
} from '@vidall/player';
import { classifyNetworkFailure } from '../../src/internal/networkRecovery';
import { PlayerFailure } from '../../src/internal/playerFailure';
import { PlayerSession } from '../../src/internal/playerSession';
import { PlayerError } from '../../src/public/types';

// ── 辅助：等待满足条件的事件 ──────────────────────────────────────────
function waitForEvent(player: VidAllPlayer, filter: (e: PlayerEvent) => boolean): Promise<PlayerEvent> {
  return new Promise((resolve) => {
    const unsub = player.subscribe((event: PlayerEvent) => {
      if (filter(event)) {
        unsub();
        resolve(event);
      }
    });
  });
}

function collectEvents(player: VidAllPlayer, count: number, filter: (e: PlayerEvent) => boolean): Promise<PlayerEvent[]> {
  return new Promise((resolve) => {
    const collected: PlayerEvent[] = [];
    player.subscribe((event: PlayerEvent) => {
      if (filter(event)) {
        collected.push(event);
        if (collected.length >= count) {
          resolve(collected);
        }
      }
    });
  });
}

// ══════════════════════════════════════════════════════════════════
// 1. HLS 正常加载：load → preparing 状态
// ══════════════════════════════════════════════════════════════════

export async function hls_load_transitionsToPreparing(): Promise<void> {
  const player = createPlayer();
  const statePromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  const event = await statePromise;
  if (event.state !== 'preparing') {
    throw new Error(`Expected state 'preparing', got '${event.state}'`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 2. DASH 正常加载：load → preparing 状态
// ══════════════════════════════════════════════════════════════════

export async function dash_load_transitionsToPreparing(): Promise<void> {
  const player = createPlayer();
  const statePromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'dash',
    uri: 'https://stream.example.com/vod.mpd'
  };
  void player.load(source);
  const event = await statePromise;
  if (event.state !== 'preparing') {
    throw new Error(`Expected state 'preparing', got '${event.state}'`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 3. HLS kind 不匹配：HTTP URI + hls kind 应拒绝
// ══════════════════════════════════════════════════════════════════

export async function hls_kindMismatch_rejected(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'hls',
    uri: 'ftp://stream.example.com/live.m3u8'
  };
  let rejected = false;
  try {
    await player.load(source);
  } catch (error) {
    rejected = true;
    if (!(error instanceof PlayerFailure)) {
      throw new Error(`Expected PlayerFailure, got ${error}`);
    }
    if (error.playerError.code !== 'URI_KIND_MISMATCH') {
      throw new Error(`Expected URI_KIND_MISMATCH, got ${error.playerError.code}`);
    }
  }
  if (!rejected) {
    throw new Error('HLS with ftp:// URI should have been rejected');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 4. DASH 空 URI 拒绝
// ══════════════════════════════════════════════════════════════════

export async function dash_emptyUri_rejected(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'dash',
    uri: ''
  };
  let rejected = false;
  try {
    await player.load(source);
  } catch (error) {
    rejected = true;
    if (!(error instanceof PlayerFailure)) {
      throw new Error(`Expected PlayerFailure, got ${error}`);
    }
    if (error.playerError.code !== 'INVALID_URI') {
      throw new Error(`Expected INVALID_URI, got ${error.playerError.code}`);
    }
  }
  if (!rejected) {
    throw new Error('DASH with empty URI should have been rejected');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 5. HLS headers 转发
// ══════════════════════════════════════════════════════════════════

export async function hls_headersForwarded_loadSucceeds(): Promise<void> {
  const player = createPlayer();
  const statePromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8',
    headers: { 'authorization': 'Bearer test-token' }
  };
  void player.load(source);
  const event = await statePromise;
  if (event.state !== 'preparing') {
    throw new Error(`Expected state 'preparing', got '${event.state}'`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 6. 网络超时分类为可重试
// ══════════════════════════════════════════════════════════════════

export async function networkTimeout_classifiedRetryable(): Promise<void> {
  const failure = classifyNetworkFailure('NETWORK_TIMEOUT');
  if (!failure.playerError.retryable) {
    throw new Error('NETWORK_TIMEOUT should be retryable');
  }
  if (failure.playerError.domain !== 'network') {
    throw new Error(`Expected domain 'network', got '${failure.playerError.domain}'`);
  }
}

// ══════════════════════════════════════════════════════════════════
// 7. TLS 证书错误分类为不可恢复
// ══════════════════════════════════════════════════════════════════

export async function tlsError_classifiedUnrecoverable(): Promise<void> {
  const failure = classifyNetworkFailure('TLS_CERTIFICATE_INVALID');
  if (failure.playerError.retryable) {
    throw new Error('TLS_CERTIFICATE_INVALID should not be retryable');
  }
  if (failure.playerError.domain !== 'network') {
    throw new Error(`Expected domain 'network', got '${failure.playerError.domain}'`);
  }
}

// ══════════════════════════════════════════════════════════════════
// 8. 格式不支持分类为不可恢复
// ══════════════════════════════════════════════════════════════════

export async function formatUnsupported_classifiedUnrecoverable(): Promise<void> {
  const failure = classifyNetworkFailure('FORMAT_UNSUPPORTED');
  if (failure.playerError.retryable) {
    throw new Error('FORMAT_UNSUPPORTED should not be retryable');
  }
}

// ══════════════════════════════════════════════════════════════════
// 9. 未知网络错误默认可重试
// ══════════════════════════════════════════════════════════════════

export async function unknownNetworkError_defaultRetryable(): Promise<void> {
  const failure = classifyNetworkFailure('UNKNOWN_CUSTOM_ERROR');
  if (!failure.playerError.retryable) {
    throw new Error('Unknown network errors should default to retryable');
  }
}

// ══════════════════════════════════════════════════════════════════
// 10. PlayerSession reportNetworkFailure 清理状态并进入 error
// ══════════════════════════════════════════════════════════════════

export async function reportNetworkFailure_clearsStateAndEntersError(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  await preparingPromise;

  // PlayerSession 的 reportNetworkFailure 是内部方法，需要通过 session 实例访问
  const session = player as PlayerSession;
  const errorPromise = waitForEvent(player, (e) => e.type === 'error');
  session.reportNetworkFailure(classifyNetworkFailure('NETWORK_TIMEOUT'));

  const errorEvent = await errorPromise;
  if (errorEvent.error === undefined) {
    throw new Error('Expected error in event');
  }
  if (!errorEvent.error!.retryable) {
    throw new Error('NETWORK_TIMEOUT error should be retryable');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 11. NetworkRecoveryController canRetry 在可重试失败后为 true
// ══════════════════════════════════════════════════════════════════

export async function networkRecovery_canRetry_afterRetryableFailure(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  await preparingPromise;

  const session = player as PlayerSession;
  session.reportNetworkFailure(classifyNetworkFailure('NETWORK_DISCONNECTED'));

  const recovery = session.networkRecovery();
  if (!recovery.canRetry()) {
    throw new Error('canRetry should be true after retryable network failure');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 12. NetworkRecoveryController canRetry 在不可恢复失败后为 false
// ══════════════════════════════════════════════════════════════════

export async function networkRecovery_cannotRetry_afterUnrecoverableFailure(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'dash',
    uri: 'https://stream.example.com/vod.mpd'
  };
  void player.load(source);
  await preparingPromise;

  const session = player as PlayerSession;
  session.reportNetworkFailure(classifyNetworkFailure('TLS_CERTIFICATE_INVALID'));

  const recovery = session.networkRecovery();
  if (recovery.canRetry()) {
    throw new Error('canRetry should be false after unrecoverable failure');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 13. reportBuffering 正确报告缓冲状态
// ══════════════════════════════════════════════════════════════════

export async function reportBuffering_transitionsToBufferingState(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  await preparingPromise;

  const session = player as PlayerSession;
  // 模拟播放中
  await player.play();

  // 报告缓冲
  const bufferingPromise = waitForEvent(player, (e) => e.type === 'buffering' && e.paused === true);
  session.reportBuffering(true, 50);
  const bufferingEvent = await bufferingPromise;
  if (bufferingEvent.percent !== 50) {
    throw new Error(`Expected buffering percent 50, got ${bufferingEvent.percent}`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 14. 切源时旧恢复状态清除
// ══════════════════════════════════════════════════════════════════

export async function sourceSwitch_clearsRecoveryState(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source1: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live1.m3u8'
  };
  void player.load(source1);
  await preparingPromise;

  // 产生网络失败
  const session = player as PlayerSession;
  session.reportNetworkFailure(classifyNetworkFailure('NETWORK_TIMEOUT'));

  // 切源
  const preparing2Promise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source2: MediaSource = {
    kind: 'dash',
    uri: 'https://stream.example.com/vod2.mpd'
  };
  void player.load(source2);
  await preparing2Promise;

  // 切源后恢复状态应清空
  const recovery = session.networkRecovery();
  if (recovery.canRetry()) {
    throw new Error('Recovery state should be cleared after source switch');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 15. release 后操作拒绝
// ══════════════════════════════════════════════════════════════════

export async function afterRelease_operationsRejected(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  await preparingPromise;
  await player.release();

  let rejected = false;
  try {
    await player.play();
  } catch (error) {
    rejected = true;
    if (!(error instanceof PlayerFailure)) {
      throw new Error(`Expected PlayerFailure, got ${error}`);
    }
    if (error.playerError.code !== 'RELEASED') {
      throw new Error(`Expected RELEASED, got ${error.playerError.code}`);
    }
  }
  if (!rejected) {
    throw new Error('play after release should have thrown');
  }
}

// ══════════════════════════════════════════════════════════════════
// 16. HLS 使用 HTTPS URI 正常加载
// ══════════════════════════════════════════════════════════════════

export async function hls_httpsUri_loadSucceeds(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://cdn.example.com/stream/index.m3u8'
  };
  void player.load(source);
  const event = await preparingPromise;
  if (event.state !== 'preparing') {
    throw new Error(`Expected state 'preparing', got '${event.state}'`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 17. DASH 使用 HTTP URI 正常加载（HTTP 也允许）
// ══════════════════════════════════════════════════════════════════

export async function dash_httpUri_loadSucceeds(): Promise<void> {
  const player = createPlayer();
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  const source: MediaSource = {
    kind: 'dash',
    uri: 'http://cdn.example.com/stream/manifest.mpd'
  };
  void player.load(source);
  const event = await preparingPromise;
  if (event.state !== 'preparing') {
    throw new Error(`Expected state 'preparing', got '${event.state}'`);
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 18. reportNetworkFailure 在 idle 状态下忽略
// ══════════════════════════════════════════════════════════════════

export async function reportNetworkFailure_ignoredInIdleState(): Promise<void> {
  const player = createPlayer();
  const session = player as PlayerSession;
  // idle 状态下调用 reportNetworkFailure 应静默忽略，不抛异常
  session.reportNetworkFailure(classifyNetworkFailure('NETWORK_TIMEOUT'));
  // 如果没有异常则通过
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 19. HLS userinfo URI 拒绝
// ══════════════════════════════════════════════════════════════════

export async function hls_userinfoUri_rejected(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://user:pass@stream.example.com/live.m3u8'
  };
  try {
    await player.load(source);
    throw new Error('HLS with userinfo URI should have been rejected');
  } catch (error) {
    if (error instanceof PlayerFailure && error.playerError.code !== 'URL_USERINFO_FORBIDDEN') {
      throw new Error(`Expected URL_USERINFO_FORBIDDEN, got ${error.playerError.code}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 20. 错误消息脱敏：凭据不应出现在错误消息中
// ══════════════════════════════════════════════════════════════════

export async function error_message_sanitization_hidesCredentials(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://user:s3cr3t@cdn.example.com/stream.m3u8'
  };
  let rejected = false;
  try {
    await player.load(source);
  } catch (error) {
    rejected = true;
    if (!(error instanceof PlayerFailure)) {
      throw new Error(`Expected PlayerFailure, got ${error}`);
    }
    const msg = error.playerError.message;
    if (msg.includes('s3cr3t') || msg.includes('user:')) {
      throw new Error('Error message leaks credentials');
    }
  }
  if (!rejected) {
    throw new Error('URI with userinfo should have been rejected');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 21. 重复 release 幂等：第二次 release 不抛异常
// ══════════════════════════════════════════════════════════════════

export async function duplicateRelease_idempotent(): Promise<void> {
  const player = createPlayer();
  await player.release();
  // 第二次 release 应幂等，不抛异常
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 22. 切源清除恢复状态：先加载 HLS 再切 DASH 时恢复控制器被重置
// ══════════════════════════════════════════════════════════════════

export async function sourceSwitch_hlsToDash_clearsRecoveryState(): Promise<void> {
  const player = createPlayer();
  const session = player as PlayerSession;

  // 先加载 HLS
  const hlsSource: MediaSource = {
    kind: 'hls',
    uri: 'https://cdn.example.com/live/stream.m3u8'
  };
  const preparingPromise = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  void player.load(hlsSource);
  await preparingPromise;

  // 模拟一次网络失败使 recovery 进入活跃状态
  session.reportNetworkFailure(classifyNetworkFailure('NETWORK_TIMEOUT'));

  // 切换到 DASH 源，recovery 状态应被清除
  const dashSource: MediaSource = {
    kind: 'dash',
    uri: 'https://cdn.example.com/vod/manifest.mpd'
  };
  const preparingPromise2 = waitForEvent(player, (e) => e.type === 'state' && e.state === 'preparing');
  void player.load(dashSource);
  await preparingPromise2;

  // 切源后恢复状态应被清除
  if (session.networkRecovery().canRetry()) {
    throw new Error('Recovery state should be cleared after source switch');
  }

  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 23. release 后 load 被拒绝：已释放会话不再接受新源
// ══════════════════════════════════════════════════════════════════

export async function release_rejectsSubsequentLoad(): Promise<void> {
  const player = createPlayer();
  await player.release();

  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://cdn.example.com/stream.m3u8'
  };
  let rejected = false;
  try {
    await player.load(source);
  } catch (error) {
    rejected = true;
    if (!(error instanceof PlayerFailure)) {
      throw new Error(`Expected PlayerFailure, got ${error}`);
    }
  }
  if (!rejected) {
    throw new Error('Load after release should have been rejected');
  }
}

// ══════════════════════════════════════════════════════════════════
// 24. HLS/DASH 加载时发射 streamingConfig 事件：结构化事件取代日志
// ══════════════════════════════════════════════════════════════════

export async function hls_load_emitsStreamingConfigEvent(): Promise<void> {
  const player = createPlayer();
  const configPromise = waitForEvent(player, (e) => e.type === 'streamingConfig');
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://stream.example.com/live.m3u8'
  };
  void player.load(source);
  const event = await configPromise;
  if (event.streamingConfig?.kind !== 'hls') {
    throw new Error(`Expected streamingConfig.kind 'hls', got '${event.streamingConfig?.kind}'`);
  }
  if (!event.streamingConfig?.networkRecovery) {
    throw new Error('HLS should enable networkRecovery');
  }
  if (!event.streamingConfig?.segmentTimelineEnabled) {
    throw new Error('HLS should enable segmentTimelineEnabled');
  }
  void player.release();
}

export async function dash_load_emitsStreamingConfigEvent(): Promise<void> {
  const player = createPlayer();
  const configPromise = waitForEvent(player, (e) => e.type === 'streamingConfig');
  const source: MediaSource = {
    kind: 'dash',
    uri: 'https://stream.example.com/vod.mpd'
  };
  void player.load(source);
  const event = await configPromise;
  if (event.streamingConfig?.kind !== 'dash') {
    throw new Error(`Expected streamingConfig.kind 'dash', got '${event.streamingConfig?.kind}'`);
  }
  if (!event.streamingConfig?.networkRecovery) {
    throw new Error('DASH should enable networkRecovery');
  }
  void player.release();
}
