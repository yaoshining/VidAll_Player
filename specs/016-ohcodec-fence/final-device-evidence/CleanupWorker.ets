import { worker, MessageEvents } from '@kit.ArkTS';
import nativeSession, { NativePlayerEvent, NativeSessionResult } from 'libvidall_player_native.so';

interface StartMessage { surface: string; uri: string; }
const port = worker.workerPort;
let events = 0;
function report(text: string): void { port.postMessage(text); }
function requireOk(result: NativeSessionResult, stage: string): void {
  if (!result.ok) { throw new Error(stage + ':' + result.code); }
}
async function start(message: StartMessage): Promise<void> {
  const result = await nativeSession.createSession('', 'no');
  requireOk(result, 'create');
  const handle = result.handle;
  requireOk(nativeSession.setEventCallback(handle, (event: NativePlayerEvent): void => {
    events++;
    if (event.type === 'videoParams' || event.type === 'error' || event.type === 'state' ||
      (event.type === 'position' && events % 10 === 0)) {
      report(event.type + '=' + event.message);
    }
  }), 'callback');
  requireOk(await nativeSession.attachSurface(handle, message.surface, 1, 480, 270), 'attach');
  requireOk(await nativeSession.load(handle, message.uri, '', '', ''), 'load');
  requireOk(await nativeSession.play(handle), 'play');
  report('ready handle=' + handle + ' hwdec=no surface=' + message.surface);
  // 不调用 releaseSession：让真正的 Worker NAPI 环境清理钩子处理活动会话。
}
port.onmessage = (event: MessageEvents): void => {
  start(event.data as StartMessage).catch((error: Error) => report('FAIL ' + error.message));
};
