import { common } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';
import nativeSession, { NativeSessionResult } from 'libvidall_player_native.so';

export interface PlayerRuntimeOptions {
  terminalPolicy: 'controlled-app-exit';
  deadlineMs: number;
}
export interface PlayerTerminalInfo {
  stage: number;
  platformError: number;
  firstObservedMs: number;
  deadlineMs: number;
  ownerTag: string;
}
export interface PlayerRuntimeStatus {
  state: 'unconfigured' | 'configuring' | 'ready' | 'failed' | 'terminal';
  terminal?: PlayerTerminalInfo;
}
class TerminalListener {
  callback: (info: PlayerTerminalInfo) => void;
  delivered: boolean = false;
  constructor(callback: (info: PlayerTerminalInfo) => void) { this.callback = callback; }
}
const listeners: TerminalListener[] = [];
let configuration: string = '';
let pending: Promise<PlayerRuntimeStatus> | undefined;
let timer: number = -1;
let cachedTerminal: PlayerTerminalInfo | undefined;
function notify(info: PlayerTerminalInfo): void {
  cachedTerminal = info;
  if (timer >= 0) { clearInterval(timer); timer = -1; }
  const current = listeners.slice();
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
  if (cachedTerminal !== undefined) return { state: 'terminal', terminal: cachedTerminal };
  const status = JSON.parse(nativeSession.getRuntimeStatus()) as PlayerRuntimeStatus;
  if (status.terminal !== undefined) notify(status.terminal);
  return status;
}
export function onPlayerTerminal(callback: (info: PlayerTerminalInfo) => void): () => void {
  const listener = new TerminalListener(callback);
  listeners.push(listener);
  const status = getPlayerRuntimeStatus();
  if (status.terminal !== undefined) notify(status.terminal);
  return (): void => { const i = listeners.indexOf(listener); if (i >= 0) listeners.splice(i, 1); };
}
export function assertPlayerRuntimeReady(): void {
  const status = getPlayerRuntimeStatus();
  if (status.state !== 'ready') throw new Error(status.state === 'terminal' ? 'PLAYER_TERMINAL' : 'RUNTIME_NOT_READY');
}
export function playerTerminalError(): Error | undefined {
  return getPlayerRuntimeStatus().state === 'terminal' ? new Error('PLAYER_TERMINAL') : undefined;
}
export function initializePlayerRuntime(context: common.Context, options: PlayerRuntimeOptions): Promise<PlayerRuntimeStatus> {
  if (options.terminalPolicy !== 'controlled-app-exit' || !Number.isInteger(options.deadlineMs) ||
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
  pending = (async (): Promise<PlayerRuntimeStatus> => {
    let resource: Uint8Array;
    try { resource = await context.resourceManager.getRawFileContent('vidall-runtime/smb.conf'); }
    catch (_) { nativeSession.rejectRuntimeResources(); throw new Error('RUNTIME_RESOURCE_FAILED'); }
    const text = new util.TextDecoder('utf-8').decodeToString(resource);
    const result: NativeSessionResult = await nativeSession.configureRuntime(context.filesDir, text, options.deadlineMs);
    if (!result.ok) throw new Error(result.code);
    assertPlayerRuntimeReady();
    if (timer < 0) timer = setInterval(() => { getPlayerRuntimeStatus(); }, 50);
    return getPlayerRuntimeStatus();
  })();
  return pending;
}
