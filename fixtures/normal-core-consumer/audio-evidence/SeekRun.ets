export interface SeekSample { positionMs: number; paused: boolean; buffering: boolean; }
export interface SeekPort {
  snapshot: () => Promise<SeekSample>;
  delay: (ms: number) => Promise<void>;
  record: (event: string, value: string) => void;
}

// time-pos在seek期间可能先显示目标，再回落到实际关键帧；不能以目标值作为推进起点。
export async function verifySeekProgress(port: SeekPort, target: number): Promise<void> {
  let previous: SeekSample | undefined;
  let settled: SeekSample | undefined;
  let reached = false;
  for (let i = 0; i < 20; i++) {
    if (i > 0) await port.delay(150);
    const current = await port.snapshot();
    if (!Number.isFinite(current.positionMs)) throw new Error('SEEK_DIAGNOSTIC_INVALID');
    const nearTarget = Math.abs(current.positionMs - target) <= 1500;
    const eligible = !current.paused && !current.buffering && nearTarget;
    reached = reached || nearTarget;
    if (eligible && previous !== undefined && current.positionMs - previous.positionMs >= 50) {
      settled = current; break;
    }
    previous = eligible ? current : undefined;
  }
  if (settled === undefined) throw new Error(reached ? 'SEEK_NOT_ADVANCING' : 'SEEK_TARGET_MISMATCH');
  port.record('seek-playback-observed', JSON.stringify(settled));
  await port.delay(700);
  const after = await port.snapshot();
  if (!Number.isFinite(after.positionMs)) throw new Error('SEEK_DIAGNOSTIC_INVALID');
  port.record('seek-check', JSON.stringify({ target, settled, after }));
  if (after.paused || after.buffering || after.positionMs < settled.positionMs + 250) throw new Error('SEEK_NOT_ADVANCING');
  port.record('seek-verified', JSON.stringify({ target, reached: settled.positionMs, after: after.positionMs }));
}
