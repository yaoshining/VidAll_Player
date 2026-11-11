import { common } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';
import nativeSession, { NativeSessionResult } from 'libvidall_player_native.so';

export interface PlayerRuntimeOptions {
  terminalPolicy: 'controlled-app-exit' | 'preserve-host';
  deadlineMs: number;
}
export interface PlayerFaultAttribution {
  state: 'known' | 'unknown';
  sessionId?: string;
  loadGeneration?: string;
}
export interface PlayerTerminalInfo {
  stage: number;
  platformError: number;
  firstObservedMs: number;
  deadlineMs: number;
  ownerTag: string;
  attribution?: PlayerFaultAttribution;
}
export interface PlayerRecoveryStatus {
  state: 'pending' | 'ready' | 'timeout';
  generation: number;
}
export interface PlayerFaultInfo {
  sequence: number;
  kind: 'session-quarantined' | 'process-terminal';
  stage: number;
  platformError: number;
  attribution: PlayerFaultAttribution;
}
export interface PlayerRuntimeStatus {
  state: 'unconfigured' | 'configuring' | 'ready' | 'failed' | 'terminal';
  terminal?: PlayerTerminalInfo;
  recovery?: PlayerRecoveryStatus;
  faults?: PlayerFaultInfo[];
}
class TerminalListener {
  callback: (info: PlayerTerminalInfo) => void;
  delivered: boolean = false;
  constructor(callback: (info: PlayerTerminalInfo) => void) { this.callback = callback; }
}
class FaultListener {
  callback: (info: PlayerFaultInfo) => void;
  sequence: number = 0;
  constructor(callback: (info: PlayerFaultInfo) => void) { this.callback = callback; }
}
const faultListeners: FaultListener[] = [];
function notifyFaults(history: PlayerFaultInfo[] | undefined): void {
  if (history === undefined) return;
  for (const info of history) {
    for (const listener of faultListeners.slice()) {
      if (info.sequence <= listener.sequence) continue;
      listener.sequence = info.sequence;
      try { listener.callback(info); } catch (_) {
        console.error('VidAllPlayer: fault listener failed');
      }
    }
  }
}
// 重放有界历史；与某个 Player 的释放生命周期无关，宿主不再需要时应取消订阅。
export function onPlayerFault(callback: (info: PlayerFaultInfo) => void): () => void {
  const listener = new FaultListener(callback);
  faultListeners.push(listener);
  getPlayerRuntimeStatus();
  return (): void => { const i = faultListeners.indexOf(listener); if (i >= 0) faultListeners.splice(i, 1); };
}
const listeners: TerminalListener[] = [];
let configuration: string = '';
let pending: Promise<PlayerRuntimeStatus> | undefined;
let timer: number = -1;
let preserveHost: boolean = false;
let cachedTerminal: PlayerTerminalInfo | undefined;
function notify(info: PlayerTerminalInfo): void {
  if (cachedTerminal === undefined) cachedTerminal = info;
  if (!preserveHost && timer >= 0) { clearInterval(timer); timer = -1; }
  // 全局终局不可复位；投递前移走本批，避免旧 Player 被全局表持有。
  const current = listeners.splice(0);
  for (const listener of current) {
    if (!listener.delivered) {
      listener.delivered = true;
      try { listener.callback(info); } catch (_) {
        // 一个宿主订阅者失败不阻止其他订阅者；native deadline 不依赖这里。
        console.error('VidAllPlayer: terminal listener failed');
      }
    }
  }
}
export function getPlayerRuntimeStatus(): PlayerRuntimeStatus {
  if (cachedTerminal !== undefined && !preserveHost) return { state: 'terminal', terminal: cachedTerminal };
  const status = JSON.parse(nativeSession.getRuntimeStatus()) as PlayerRuntimeStatus;
  if (status.recovery !== undefined) preserveHost = true;
  notifyFaults(status.faults);
  if (status.terminal !== undefined) {
    if (cachedTerminal === undefined) notify(status.terminal);
    status.terminal = cachedTerminal;
  }
  return status;
}
export function onPlayerTerminal(callback: (info: PlayerTerminalInfo) => void): () => void {
  const listener = new TerminalListener(callback);
  listeners.push(listener);
  const status = getPlayerRuntimeStatus();
  if (status.terminal !== undefined) notify(status.terminal);
  return (): void => { const i = listeners.indexOf(listener); if (i >= 0) listeners.splice(i, 1); };
}
// generation 在实例创建时固定，不能在每个命令上改用当前全局代。
export function capturePlayerRuntimeGeneration(compatible: boolean = false): number {
  const status = getPlayerRuntimeStatus();
  if (status.state === 'ready') return 1;
  if (status.state === 'terminal' && compatible && status.recovery !== undefined) {
    if (status.recovery.state === 'ready' && status.recovery.generation > 1) return status.recovery.generation;
    throw new Error('PLAYER_RECOVERY_PENDING');
  }
  throw new Error(status.state === 'terminal' ? 'PLAYER_TERMINAL' : 'RUNTIME_NOT_READY');
}
export function assertPlayerRuntimeReady(generation: number = 1, compatible: boolean = false): void {
  const status = getPlayerRuntimeStatus();
  const error = terminalError(status, generation, compatible);
  if (error !== undefined) throw error;
  if (status.state !== 'ready' && status.state !== 'terminal') throw new Error('RUNTIME_NOT_READY');
}
export function playerTerminalError(generation: number = 1, compatible: boolean = false): Error | undefined {
  return terminalError(getPlayerRuntimeStatus(), generation, compatible);
}
function terminalError(status: PlayerRuntimeStatus, generation: number, compatible: boolean): Error | undefined {
  if (status.state !== 'terminal') return undefined;
  if (compatible && generation > 1 && status.recovery?.state === 'ready' &&
    status.recovery.generation === generation) return undefined;
  return new Error('PLAYER_TERMINAL');
}
export function initializePlayerRuntime(context: common.Context, options: PlayerRuntimeOptions): Promise<PlayerRuntimeStatus> {
  if ((options.terminalPolicy !== 'controlled-app-exit' && options.terminalPolicy !== 'preserve-host') || !Number.isInteger(options.deadlineMs) ||
    options.deadlineMs < 1000 || options.deadlineMs > 10000 || !context.filesDir) {
    return Promise.reject(new Error('RUNTIME_CONFIG_INVALID'));
  }
  const key = context.filesDir + '\n' + options.terminalPolicy + '\n' + options.deadlineMs;
  if (configuration.length > 0) {
    if (configuration !== key) return Promise.reject(new Error('RUNTIME_CONFIG_CONFLICT'));
    if (getPlayerRuntimeStatus().state === 'terminal') return Promise.reject(new Error('PLAYER_TERMINAL'));
    if (pending !== undefined) return pending;
  }
  configuration = key;
  preserveHost = options.terminalPolicy === 'preserve-host';
  pending = (async (): Promise<PlayerRuntimeStatus> => {
    let resource: Uint8Array;
    try { resource = await context.resourceManager.getRawFileContent('vidall-runtime/smb.conf'); }
    catch (_) { nativeSession.rejectRuntimeResources(); throw new Error('RUNTIME_RESOURCE_FAILED'); }
    const text = new util.TextDecoder('utf-8').decodeToString(resource);
    const result: NativeSessionResult = await nativeSession.configureRuntime(context.filesDir, text, options.deadlineMs, options.terminalPolicy);
    if (!result.ok) throw new Error(result.code);
    assertPlayerRuntimeReady();
    if (timer < 0) timer = setInterval(() => { getPlayerRuntimeStatus(); }, 50);
    return getPlayerRuntimeStatus();
  })();
  return pending;
}
