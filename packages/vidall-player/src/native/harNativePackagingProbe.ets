import nativeSession from 'libvidall_player_native.so';

export interface HarNativePackagingResult {
  created: boolean;
  code: string;
}

// 仅供 HAR 内部构建验证使用，公开 Index.ets 不会导出该模块或其 NAPI 类型。
export function runHarNativePackagingProbe(): HarNativePackagingResult {
  const result = nativeSession.createSession();
  if (result.ok) {
    nativeSession.releaseSession(result.handle);
  }
  return { created: result.ok, code: result.code };
}
