// T052/T053：ArkTS 流媒体集成测试
// 覆盖 hls/dash/localhostProxy 正常、边界（切源释放请求、重复 release）与
// 失败路径（断网恢复、错误脱敏）。验证 MediaSource 类型分派不泄漏旧连接或旧媒体状态。
//
// TDD 红阶段：T052 先写测试，T053 实现使之通过。

import {
  createPlayer,
  MediaSource,
  PlayerEvent,
  VidAllPlayer
} from '@vidall/player';
import { PlayerFailure } from '@vidall/player/src/internal/playerFailure';

// ── 辅助：收集全部事件 ──────────────────────────────────────────
function collectEvents(player: VidAllPlayer): PlayerEvent[] {
  const events: PlayerEvent[] = [];
  player.subscribe((event: PlayerEvent) => { events.push(event); });
  return events;
}

// 原生适配层集成点：reportNetworkFailure 在 PlayerSession 上实现但不在公开接口暴露。
interface NativeBridgePlayer extends VidAllPlayer {
  reportNetworkFailure(failure: PlayerFailure): void;
}

function asBridgePlayer(player: VidAllPlayer): NativeBridgePlayer {
  return player as NativeBridgePlayer;
}

function lastStateEvent(events: PlayerEvent[]): PlayerEvent {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type === 'state') {
      return events[i];
    }
  }
  throw new Error('No state event emitted.');
}

function leaseEvents(events: PlayerEvent[]): PlayerEvent[] {
  return events.filter((e: PlayerEvent) => e.type === 'proxyLease');
}

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

// ══════════════════════════════════════════════════════════════════
// 1. HLS 正常加载：进入 preparing，不产生代理 lease 事件
// ══════════════════════════════════════════════════════════════════
export async function hlsLoad_entersPreparingNoLease(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://fixture.invalid/stream.m3u8'
  };
  await player.load(source);
  const last = lastStateEvent(events);
  assert(last.state === 'preparing', `HLS load should enter preparing, got ${last.state}`);
  assert(leaseEvents(events).length === 0, 'HLS must not emit proxy lease events');
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 2. DASH 正常加载：进入 preparing，不产生代理 lease 事件
// ══════════════════════════════════════════════════════════════════
export async function dashLoad_entersPreparingNoLease(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'dash',
    uri: 'https://fixture.invalid/stream.mpd'
  };
  await player.load(source);
  const last = lastStateEvent(events);
  assert(last.state === 'preparing', `DASH load should enter preparing, got ${last.state}`);
  assert(leaseEvents(events).length === 0, 'DASH must not emit proxy lease events');
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 3. localhostProxy 正常加载：进入 preparing 并获取 lease
// ══════════════════════════════════════════════════════════════════
export async function localhostProxyLoad_acquiresLease(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'localhostProxy',
    uri: 'http://127.0.0.1:8443/smb/share/video.mp4',
    proxyLeaseId: 'lease-001'
  };
  await player.load(source);
  const last = lastStateEvent(events);
  assert(last.state === 'preparing', `localhostProxy load should enter preparing, got ${last.state}`);
  const leases = leaseEvents(events);
  assert(leases.length === 1, `Expected 1 lease event, got ${leases.length}`);
  assert(leases[0].lease!.state === 'acquired', `Lease should be acquired, got ${leases[0].lease!.state}`);
  assert(leases[0].lease!.leaseId === 'lease-001', 'Lease id should match proxyLeaseId');
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 4. 切源释放旧 lease：加载 localhostProxy 后加载 hls，旧 lease 进入 releaseRequested
// ══════════════════════════════════════════════════════════════════
export async function sourceSwitch_releasesOldLease(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const proxySource: MediaSource = {
    kind: 'localhostProxy',
    uri: 'http://localhost:8443/smb/share/video.mp4',
    proxyLeaseId: 'lease-002'
  };
  await player.load(proxySource);
  const hlsSource: MediaSource = {
    kind: 'hls',
    uri: 'https://fixture.invalid/stream.m3u8'
  };
  events.length = 0;
  await player.load(hlsSource);
  const leases = leaseEvents(events);
  assert(leases.length >= 1, 'Source switch should emit lease release request');
  const releaseEvent = leases.find((e: PlayerEvent) => e.lease!.state === 'releaseRequested');
  assert(releaseEvent !== undefined, 'Old lease should enter releaseRequested on source switch');
  assert(releaseEvent!.lease!.leaseId === 'lease-002', 'Released lease should match old proxyLeaseId');
  const last = lastStateEvent(events);
  assert(last.state === 'preparing', `New source should enter preparing, got ${last.state}`);
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 5. 断网恢复：加载 hls → play → 上报网络失败 → error 状态且错误消息脱敏
// ══════════════════════════════════════════════════════════════════
export async function networkFailure_entersErrorAndSanitizes(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://fixture.invalid/stream.m3u8'
  };
  await player.load(source);
  await player.play();
  events.length = 0;
  const bridge = asBridgePlayer(player);
  bridge.reportNetworkFailure(new PlayerFailure({
    domain: 'network',
    code: 'NETWORK_DISCONNECTED',
    message: 'Connection lost to https://fixture.invalid/stream.m3u8?token=s3cr3t',
    retryable: true,
    context: {}
  }));
  const last = lastStateEvent(events);
  assert(last.state === 'error', `Network failure should enter error, got ${last.state}`);
  const errorEvent = events.find((e: PlayerEvent) => e.type === 'error');
  assert(errorEvent !== undefined, 'Network failure should emit error event');
  const msg = errorEvent!.error!.message;
  assert(msg.indexOf('s3cr3t') < 0, `Error message must not echo token: ${msg}`);
  assert(msg.indexOf('[REDACTED_QUERY]') >= 0, `Error message should redact query token: ${msg}`);
  await player.release();
}

// ══════════════════════════════════════════════════════════════════
// 6. 重复 release 幂等：第二次 release 不产生额外状态变更
// ══════════════════════════════════════════════════════════════════
export async function duplicateRelease_isIdempotent(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'hls',
    uri: 'https://fixture.invalid/stream.m3u8'
  };
  await player.load(source);
  await player.release();
  const eventsAfterFirstRelease = events.length;
  await player.release();
  assert(events.length === eventsAfterFirstRelease,
    `Duplicate release should not emit additional events, got ${events.length - eventsAfterFirstRelease}`);
}

// ══════════════════════════════════════════════════════════════════
// 7. release 释放 lease：加载 localhostProxy → release → lease releaseRequested + released
// ══════════════════════════════════════════════════════════════════
export async function release_requestsLeaseRelease(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'localhostProxy',
    uri: 'http://[::1]:8443/smb/share/video.mp4',
    proxyLeaseId: 'lease-003'
  };
  await player.load(source);
  events.length = 0;
  await player.release();
  const leases = leaseEvents(events);
  assert(leases.length >= 1, 'Release should emit lease release request');
  const releaseEvent = leases.find((e: PlayerEvent) => e.lease!.state === 'releaseRequested');
  assert(releaseEvent !== undefined, 'Lease should enter releaseRequested on release');
  const last = lastStateEvent(events);
  assert(last.state === 'released', `Player should enter released, got ${last.state}`);
}

// ══════════════════════════════════════════════════════════════════
// 8. localhostProxy 非 loopback 被拒绝：校验在 load 阶段失败并进入 error
// ══════════════════════════════════════════════════════════════════
export async function nonLoopbackProxy_rejectedAtLoad(): Promise<void> {
  const player = createPlayer();
  const events = collectEvents(player);
  const source: MediaSource = {
    kind: 'localhostProxy',
    uri: 'http://evil.invalid:8443/smb/share/video.mp4',
    proxyLeaseId: 'lease-004'
  };
  let threw = false;
  try {
    await player.load(source);
  } catch (_) {
    threw = true;
  }
  assert(threw, 'Non-loopback localhostProxy should be rejected');
  const errorEvent = events.find((e: PlayerEvent) => e.type === 'error');
  assert(errorEvent !== undefined, 'Rejected load should emit error event');
  assert(leaseEvents(events).length === 0, 'Rejected load must not acquire a lease');
  await player.release();
}
