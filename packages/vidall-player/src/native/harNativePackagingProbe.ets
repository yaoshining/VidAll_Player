import harNativeProbe, { ProbeCallback } from 'libvidall_player_native.so';

export interface HarNativeProbeResult {
  commandResult: string;
  callbackResult: string;
}

// 仅供 HAR 内部验证使用，公开 Index.ets 不会导出该模块或其 NAPI 类型。
export function runHarNativePackagingProbe(): HarNativeProbeResult {
  let callbackResult = '';
  const callback: ProbeCallback = (message: string): void => {
    callbackResult = message;
  };
  const commandResult: string = harNativeProbe.setCallback(callback);
  return { commandResult: `${harNativeProbe.ping()}:${commandResult}`, callbackResult };
}
