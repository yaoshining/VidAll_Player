import { PlayerDiagnosticsSnapshot } from '@vidall/player';

export interface ProbeTimings { count: number; medianMs: number; p95Ms: number; maxMs: number; }
export function summarizeTimings(values: number[]): ProbeTimings {
  const sorted = values.slice().sort((a: number, b: number): number => a - b);
  return { count: sorted.length, medianMs: sorted[Math.max(0, Math.ceil(sorted.length / 2) - 1)] ?? 0,
    p95Ms: sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)] ?? 0, maxMs: sorted[sorted.length - 1] ?? 0 };
}
export function validateProbeSnapshot(snapshot: PlayerDiagnosticsSnapshot, width: number, height: number): string[] {
  const failures: string[] = [];
  if (snapshot.schemaVersion !== 1) failures.push('schemaVersion');
  if (snapshot.fields.videoInputWidth?.value !== width) failures.push('videoInputWidth');
  if (snapshot.fields.videoInputHeight?.value !== height) failures.push('videoInputHeight');
  if (snapshot.fields.filename?.status === 'available') failures.push('filename privacy');
  if (snapshot.fields.mediaTitle?.status === 'available') failures.push('mediaTitle privacy');
  return failures;
}
