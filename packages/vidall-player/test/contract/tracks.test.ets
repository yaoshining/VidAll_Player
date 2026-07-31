// T042/T044 轨道契约测试：枚举字段、选择/取消、连续切换、跳转后状态、
// 非法轨道、外挂音频 URL 与首期缓存请求的 FEATURE_UNSUPPORTED。
//
// TDD 绿阶段：T042 先写测试，T044 实现使之通过。

import {
  createPlayer,
  ExternalAudio,
  MediaSource,
  PlayerEvent,
  PlayerTrack,
  VidAllPlayer
} from '@vidall/player';

// ── 辅助：等待 N 个事件 ──────────────────────────────────────────
function waitForEvents(player: VidAllPlayer, count: number, filter: (e: PlayerEvent) => boolean): Promise<PlayerEvent[]> {
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

// ── 辅助：创建已加载媒体的基础播放器 ──────────────────────────────
function createLoadedPlayer(): { player: VidAllPlayer; tracksPromise: Promise<PlayerEvent> } {
  const player = createPlayer();
  const tracksPromise = waitForEvent(player, (e) => e.type === 'tracks');
  // 同步 load：当前内存实现直接 resolve，轨道事件在 load 内部 emit
  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/multi-track.mkv',
    externalAudio: [
      { uri: 'https://fixture.invalid/audio-eng.aac', title: 'English', language: 'eng' },
      { uri: 'https://fixture.invalid/audio-jpn.aac', title: '日本語', language: 'jpn' }
    ],
    externalSubtitles: [
      { uri: 'https://fixture.invalid/sub-zh.srt', title: '简体中文', format: 'srt' },
      { uri: 'https://fixture.invalid/sub-en.ass', title: 'English', format: 'ass' }
    ]
  };
  void player.load(source);
  return { player, tracksPromise };
}

// ══════════════════════════════════════════════════════════════════
// 1. 轨道枚举字段完整性
// ══════════════════════════════════════════════════════════════════

export async function trackEnumeration_fieldsComplete(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const event = await tracksPromise;
  const tracks: PlayerTrack[] = event.tracks!;
  // 至少应有 2 个外挂音频 + 2 个外挂字幕 = 4 条轨道
  if (tracks.length < 4) {
    throw new Error(`Expected at least 4 tracks, got ${tracks.length}`);
  }
  for (let i = 0; i < tracks.length; i++) {
    const t = tracks[i];
    // 必填字段
    if (typeof t.id !== 'number') {
      throw new Error(`Track ${i}: id must be a number`);
    }
    if (t.kind !== 'audio' && t.kind !== 'video' && t.kind !== 'subtitle') {
      throw new Error(`Track ${i}: kind must be audio|video|subtitle, got ${t.kind}`);
    }
    if (typeof t.selected !== 'boolean') {
      throw new Error(`Track ${i}: selected must be boolean`);
    }
    // recognitionStatus 四态
    const validStatuses: string[] = ['recognized', 'renderable', 'degraded', 'unsupported'];
    if (validStatuses.indexOf(t.recognitionStatus) < 0) {
      throw new Error(`Track ${i}: recognitionStatus must be one of ${validStatuses.join('|')}, got ${t.recognitionStatus}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 2. selectTrack 正常选择与取消（验证 tracks 快照）
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_selectAndDeselect(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const event = await tracksPromise;
  const audioTracks = event.tracks!.filter((t: PlayerTrack) => t.kind === 'audio');
  if (audioTracks.length < 2) {
    throw new Error('Need at least 2 audio tracks');
  }
  // 选择第一个音频轨道
  await player.selectTrack('audio', audioTracks[1].id);
  // 等待 tracks 事件快照，验证选中状态
  const afterSelect = await waitForEvent(player, (e) => e.type === 'tracks');
  const selected = afterSelect.tracks!.filter((t: PlayerTrack) => t.kind === 'audio' && t.selected);
  if (selected.length !== 1 || selected[0].id !== audioTracks[1].id) {
    throw new Error(`Expected audio track ${audioTracks[1].id} selected, got ${JSON.stringify(selected)}`);
  }
  // 取消选择
  await player.selectTrack('audio', null);
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 3. 连续切换音轨
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_consecutiveSwitches(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const event = await tracksPromise;
  const audioTracks = event.tracks!.filter((t: PlayerTrack) => t.kind === 'audio');
  if (audioTracks.length < 2) {
    throw new Error('Need at least 2 audio tracks');
  }
  // 连续切换：1 → 2 → 1，每次验证互斥
  await player.selectTrack('audio', audioTracks[0].id);
  const s1 = await waitForEvent(player, (e) => e.type === 'tracks');
  const sel1 = s1.tracks!.filter((t: PlayerTrack) => t.kind === 'audio' && t.selected);
  if (sel1.length !== 1 || sel1[0].id !== audioTracks[0].id) {
    throw new Error('First select failed');
  }

  await player.selectTrack('audio', audioTracks[1].id);
  const s2 = await waitForEvent(player, (e) => e.type === 'tracks');
  const sel2 = s2.tracks!.filter((t: PlayerTrack) => t.kind === 'audio' && t.selected);
  if (sel2.length !== 1 || sel2[0].id !== audioTracks[1].id) {
    throw new Error('Second select failed — mutual exclusion broken');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 4. 跳转后轨道状态保持
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_stateAfterSeek(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const event = await tracksPromise;
  await player.selectTrack('audio', event.tracks!.filter((t: PlayerTrack) => t.kind === 'audio')[0].id);
  const afterSelect = await waitForEvent(player, (e) => e.type === 'tracks');
  const selectedId = afterSelect.tracks!.filter((t: PlayerTrack) => t.kind === 'audio' && t.selected)[0]?.id;

  // 跳转后，轨道选择状态应保持不变
  await player.seekPercent(50);
  const afterSeek = await waitForEvent(player, (e) => e.type === 'tracks');
  const stillSelected = afterSeek.tracks!.filter((t: PlayerTrack) => t.kind === 'audio' && t.selected);
  if (stillSelected.length !== 1 || stillSelected[0].id !== selectedId) {
    throw new Error('Track selection should persist after seek');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 5. 非法轨道 ID 拒绝
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_invalidTrackIdRejected(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  await tracksPromise;
  try {
    await player.selectTrack('audio', 9999);
    throw new Error('selectTrack with non-existent id should have thrown');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('TRACK_NOT_FOUND') < 0) {
      throw new Error(`Expected TRACK_NOT_FOUND, got: ${error}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 6. 负数轨道 ID 拒绝
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_negativeTrackIdRejected(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  await tracksPromise;
  try {
    await player.selectTrack('audio', -1);
    throw new Error('selectTrack with negative id should have thrown');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('INVALID_TRACK_ID') < 0) {
      throw new Error(`Expected INVALID_TRACK_ID, got: ${error}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 7. 外挂音频 URL 必须为 HTTP/HTTPS
// ══════════════════════════════════════════════════════════════════

export async function externalAudio_mustBeHttpOrHttps(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/media.mkv'
  };
  void player.load(source);

  // ftp 外挂音频应拒绝
  const badAudio: ExternalAudio = { uri: 'ftp://fixture.invalid/audio.aac' };
  try {
    await player.addExternalAudio(badAudio);
    throw new Error('addExternalAudio with ftp:// should have thrown');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL') < 0) {
      throw new Error(`Expected UNSUPPORTED_EXTERNAL_AUDIO_PROTOCOL, got: ${error}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 8. 外挂字幕 PGS 为 recognized，SRT/ASS 为 renderable（按 title 绑定）
// ══════════════════════════════════════════════════════════════════

export async function externalSubtitle_recognitionStatusByFormat(): Promise<void> {
  const player = createPlayer();
  const tracksPromise = waitForEvent(player, (e) => e.type === 'tracks' && (e.tracks?.length ?? 0) >= 3);

  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/media.mkv',
    externalSubtitles: [
      { uri: 'https://fixture.invalid/sub.srt', title: 'SRT-简体中文', format: 'srt' },
      { uri: 'https://fixture.invalid/sub.pgs', title: 'PGS-图形字幕', format: 'pgs' },
      { uri: 'https://fixture.invalid/sub.ass', title: 'ASS-英文', format: 'ass' }
    ]
  };
  void player.load(source);

  const event = await tracksPromise;
  const subs = event.tracks!.filter((t: PlayerTrack) => t.kind === 'subtitle');

  // 按 title 精确匹配，确保格式与 recognitionStatus 对应
  const srt = subs.find((t: PlayerTrack) => t.title === 'SRT-简体中文');
  const pgs = subs.find((t: PlayerTrack) => t.title === 'PGS-图形字幕');
  const ass = subs.find((t: PlayerTrack) => t.title === 'ASS-英文');

  if (!srt) { throw new Error('SRT subtitle not found'); }
  if (srt.recognitionStatus !== 'renderable') { throw new Error(`SRT should be renderable, got ${srt.recognitionStatus}`); }

  if (!pgs) { throw new Error('PGS subtitle not found'); }
  if (pgs.recognitionStatus !== 'recognized') { throw new Error(`PGS should be recognized, got ${pgs.recognitionStatus}`); }

  if (!ass) { throw new Error('ASS subtitle not found'); }
  if (ass.recognitionStatus !== 'renderable') { throw new Error(`ASS should be renderable, got ${ass.recognitionStatus}`); }

  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 9. 字幕延迟设置
// ══════════════════════════════════════════════════════════════════

export async function setSubtitleDelay_normalAndInvalid(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  await tracksPromise;
  // 正常延迟
  await player.setSubtitleDelay(500);
  await player.setSubtitleDelay(-200);
  // 非有限值应拒绝
  try {
    await player.setSubtitleDelay(Infinity);
    throw new Error('setSubtitleDelay(Infinity) should have thrown');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('INVALID_CONTROL_VALUE') < 0) {
      throw new Error(`Expected INVALID_CONTROL_VALUE, got: ${error}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 10. 首期缓存请求稳定返回 FEATURE_UNSUPPORTED
// ══════════════════════════════════════════════════════════════════

// 缓存请求 API (requestCache) 在首期版本稳定返回 FEATURE_UNSUPPORTED，
// 确保不静默接受缓存请求。

export async function cacheRequest_returnsFeatureUnsupported(): Promise<void> {
  const player = createPlayer();
  const source: MediaSource = {
    kind: 'https',
    uri: 'https://fixture.invalid/media.mkv'
  };
  void player.load(source);

  try {
    await player.requestCache('https://fixture.invalid/sub.srt');
    throw new Error('requestCache should have thrown FEATURE_UNSUPPORTED');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('FEATURE_UNSUPPORTED') < 0) {
      throw new Error(`Expected FEATURE_UNSUPPORTED, got: ${error}`);
    }
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 11. release 后轨道操作拒绝
// ══════════════════════════════════════════════════════════════════

export async function trackOperations_rejectedAfterRelease(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  await tracksPromise;
  await player.release();
  try {
    await player.selectTrack('audio', 1);
    throw new Error('selectTrack after release should have thrown');
  } catch (error) {
    if (error instanceof Error && error.message.indexOf('SESSION_RELEASED') < 0) {
      throw new Error(`Expected SESSION_RELEASED, got: ${error}`);
    }
  }
}

// ══════════════════════════════════════════════════════════════════
// 12. tracks 事件深拷贝：后续选择不污染已投递事件
// ══════════════════════════════════════════════════════════════════

export async function tracksEvent_isDeepCopy(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const firstEvent = await tracksPromise;
  const originalTracks = firstEvent.tracks!;
  const originalSelected = originalTracks[0].selected;

  await player.selectTrack('audio', originalTracks[0].id);

  // 已投递事件中的 selected 不应被后续操作改变
  if (originalTracks[0].selected !== originalSelected) {
    throw new Error('tracks event should be a deep copy; subsequent mutations must not affect it');
  }
  void player.release();
}

// ══════════════════════════════════════════════════════════════════
// 13. selectTrack 仅影响同类别的轨道
// ══════════════════════════════════════════════════════════════════

export async function selectTrack_onlyAffectsSameKind(): Promise<void> {
  const { player, tracksPromise } = createLoadedPlayer();

  const firstEvent = await tracksPromise;
  const audioTracks = firstEvent.tracks!.filter((t: PlayerTrack) => t.kind === 'audio');
  const subTracks = firstEvent.tracks!.filter((t: PlayerTrack) => t.kind === 'subtitle');

  if (audioTracks.length < 1 || subTracks.length < 1) {
    throw new Error('Need at least one audio and one subtitle track');
  }

  const subSelectedBefore = subTracks.map((t: PlayerTrack) => t.selected);

  // 选择音频轨道
  await player.selectTrack('audio', audioTracks[0].id);
  const afterSelect = await waitForEvent(player, (e) => e.type === 'tracks');

  // 字幕轨道的 selected 不应被音频选择影响
  const subAfter = afterSelect.tracks!.filter((t: PlayerTrack) => t.kind === 'subtitle');
  for (let i = 0; i < subAfter.length && i < subSelectedBefore.length; i++) {
    if (subAfter[i].selected !== subSelectedBefore[i]) {
      throw new Error('Subtitle track selection should not change when audio track is selected');
    }
  }
  void player.release();
}