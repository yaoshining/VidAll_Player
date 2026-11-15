export interface FocusSnapshot { paused: boolean; positionMs: number; }
export interface FocusPort {
  active: () => void;
  startAlarm: () => Promise<void>;
  stopAlarm: () => Promise<void>;
  samplesWritten: () => number;
  snapshot: () => Promise<FocusSnapshot>;
  delay: (ms: number) => Promise<void>;
  confirmManualResume: () => Promise<void>;
  resume: () => Promise<void>;
  record: (event: string) => void;
}

// 只有真实系统竞争流能触发暂停；此流程没有 Player.pause 或伪造事件入口。
export async function runFocusProbe(port: FocusPort): Promise<void> {
  port.active();
  const initial = await port.snapshot();
  if (initial.paused || !Number.isFinite(initial.positionMs)) throw new Error('FOCUS_INITIAL_NOT_PLAYING');
  try {
    await port.startAlarm(); port.active();
    let paused = await port.snapshot();
    for (let i = 0; i < 100 && !paused.paused; i++) {
      await port.delay(50); port.active(); paused = await port.snapshot();
    }
    if (!paused.paused) throw new Error('SYSTEM_PAUSE_MISSING');
    await port.delay(1500); port.active();
    const held = await port.snapshot();
    if (!held.paused || !Number.isFinite(held.positionMs) || Math.abs(held.positionMs - paused.positionMs) > 180) {
      throw new Error('SYSTEM_PAUSE_NOT_STABLE');
    }
    if (port.samplesWritten() < 48000) throw new Error('ALARM_AUDIO_NOT_WRITTEN');
    port.record('system-pause-observed');
  } finally {
    await port.stopAlarm();
    port.record('alarm-released');
  }
  await port.delay(1500); port.active();
  const stopped = await port.snapshot();
  if (!stopped.paused) throw new Error('UNEXPECTED_AUTO_RESUME');
  await port.confirmManualResume(); port.active();
  port.record('manual-resume-confirmed');
  await port.resume();
  await port.delay(3000); port.active();
  const resumed = await port.snapshot();
  if (resumed.paused || !Number.isFinite(resumed.positionMs) || resumed.positionMs < stopped.positionMs + 500) {
    throw new Error('RESUME_NOT_ADVANCING');
  }
  port.record('focus-flow-completed-audio-pending');
}
