import { PlayerDiagnosticsSnapshot, PlayerFaultInfo, PlayerLoadIdentity } from '@vidall/player';
import { requireHardware, requireSoftwareDecode } from './ProbeChecks';

export interface FenceProbeSession {
  readonly index: number;
  readonly surfaceId: string;
  readonly identity: PlayerLoadIdentity;
}

// 页面使用独立运行时监听器填充；不绑定已进入 release 的 Player 事件队列。
export class FenceFaultInbox {
  private values: PlayerFaultInfo[] = [];
  add(info: PlayerFaultInfo): void {
    if (this.values.length && info.sequence <= this.values[this.values.length - 1].sequence) return;
    if (this.values.length >= 8) throw new Error('PROBE_FAULT_LIMIT');
    this.values.push({ sequence: info.sequence, kind: info.kind, stage: info.stage, platformError: info.platformError,
      attribution: { state: info.attribution.state, sessionId: info.attribution.sessionId,
        loadGeneration: info.attribution.loadGeneration } });
  }
  after(sequence: number): PlayerFaultInfo | undefined {
    return this.values.find((value: PlayerFaultInfo): boolean => value.sequence > sequence);
  }
  count(): number { return this.values.length; }
}

export interface FenceProbePort {
  open: (index: number) => Promise<FenceProbeSession>;
  close: (session: FenceProbeSession) => Promise<void>;
  snapshot: (session: FenceProbeSession) => Promise<PlayerDiagnosticsSnapshot>;
  confirmPlayback: (session: FenceProbeSession) => Promise<void>;
  returnToList: (session: FenceProbeSession) => Promise<void>;
  nextFault: (afterSequence: number) => Promise<PlayerFaultInfo>;
  faultCount: () => number;
  runtimeState: () => string;
  confirmLateClose: () => Promise<void>;
  record: (event: string, value?: string) => void;
}

function ready(port: FenceProbePort): void {
  if (port.runtimeState() !== 'ready') throw new Error('RUNTIME_NOT_READY');
}
function faultCount(port: FenceProbePort, count: number): void {
  if (port.faultCount() !== count) throw new Error('UNEXPECTED_FAULT_COUNT');
}
function sameFault(info: PlayerFaultInfo, session: FenceProbeSession, afterSequence: number): void {
  if (info.sequence <= afterSequence || info.kind !== 'session-quarantined' || info.stage !== 1 ||
    info.platformError !== -4 || info.attribution.state !== 'known' ||
    info.attribution.sessionId !== session.identity.sessionId ||
    info.attribution.loadGeneration !== session.identity.loadGeneration) throw new Error('CLOSE_FAULT_MISMATCH');
}

export async function runFenceProbe(port: FenceProbePort): Promise<void> {
  const sessions: FenceProbeSession[] = [];
  const open = async (index: number): Promise<FenceProbeSession> => {
    ready(port);
    const opened = await port.open(index);
    // 固定每次 load 的回执，不使用当前页面的可变“正在播放”身份。
    const session: FenceProbeSession = { index: opened.index, surfaceId: opened.surfaceId,
      identity: { sessionId: opened.identity.sessionId, loadGeneration: opened.identity.loadGeneration } };
    if (session.index !== index || !session.identity.sessionId || !session.identity.loadGeneration) {
      throw new Error('LOAD_IDENTITY_REQUIRED');
    }
    if (!session.surfaceId || sessions.some((old: FenceProbeSession): boolean => old.surfaceId === session.surfaceId)) {
      throw new Error('FRESH_SURFACE_REQUIRED');
    }
    if (sessions.some((old: FenceProbeSession): boolean => old.identity.sessionId === session.identity.sessionId)) {
      throw new Error('FRESH_SESSION_REQUIRED');
    }
    sessions.push(session);
    const snapshot = await port.snapshot(session);
    port.record('playback-observed', JSON.stringify({ index, identity: session.identity,
      backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));
    if (index < 4) requireHardware(snapshot); else requireSoftwareDecode(snapshot);
    port.record('playback-path', JSON.stringify({ index, identity: session.identity,
      backend: snapshot.fields.renderBackend, decoder: snapshot.fields.hardwareDecoder }));
    await port.confirmPlayback(session);
    ready(port);
    return session;
  };
  ready(port); faultCount(port, 0);
  const first = await open(1);
  await port.close(first);
  port.record('release-interface-completed', '1');
  const firstFault = await port.nextFault(0);
  sameFault(firstFault, first, 0); ready(port); faultCount(port, 1);
  port.record('close-fault-confirmed', JSON.stringify(firstFault));
  await port.returnToList(first);
  port.record('returned-after-close-fault', '1');
  const second = await open(2);
  await port.close(second);
  port.record('release-interface-completed', '2');
  ready(port); faultCount(port, 1);
  port.record('awaiting-native-late-close-log');
  // release 在 5 秒后返回；实际 close 的 7 秒延时仍可能未结束。
  // 必须先核对本轮同 PID 的原生日志；这个确认本身不证明硬解名额已归还。
  await port.confirmLateClose();
  ready(port); faultCount(port, 1);
  const third = await open(3);
  port.record('late-close-slot-reclaimed');
  await port.close(third);
  port.record('release-interface-completed', '3');
  const thirdFault = await port.nextFault(firstFault.sequence);
  sameFault(thirdFault, third, firstFault.sequence); ready(port); faultCount(port, 2);
  port.record('close-fault-confirmed', JSON.stringify(thirdFault));
  await port.returnToList(third);
  port.record('returned-after-close-fault', '3');
  const fourth = await open(4);
  port.record('isolation-limit-software-fallback');
  await port.close(fourth);
  port.record('release-interface-completed', '4');
  ready(port); faultCount(port, 2);
  // 仅流程门槛完成；同 PID 原生日志、画面和可听音频仍由设备证据验收。
  port.record('probe-flow-completed');
}
