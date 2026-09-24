import { PlayerDiagnosticsSnapshot } from '@vidall/player';

export interface ProbeTimings { count: number; medianMs: number; p95Ms: number; maxMs: number; }
export function summarizeTimings(values: number[]): ProbeTimings {
  const sorted = values.slice().sort((a: number, b: number): number => a - b);
  return { count: sorted.length, medianMs: sorted.length === 0 ? 0 : (sorted[Math.floor((sorted.length - 1) / 2)] + sorted[Math.floor(sorted.length / 2)]) / 2,
    p95Ms: sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)] ?? 0, maxMs: sorted[sorted.length - 1] ?? 0 };
}
export function validateProbeSnapshot(snapshot: PlayerDiagnosticsSnapshot, width: number, height: number): string[] {
  const failures: string[] = [];
  if (snapshot.schemaVersion !== 1) failures.push('schemaVersion');
  if (snapshot.fields.videoInputWidth?.status !== 'available' || snapshot.fields.videoInputWidth.value !== width) failures.push('videoInputWidth');
  if (snapshot.fields.videoInputHeight?.status !== 'available' || snapshot.fields.videoInputHeight.value !== height) failures.push('videoInputHeight');
  if (snapshot.fields.filename?.status === 'available') failures.push('filename privacy');
  if (snapshot.fields.mediaTitle?.status === 'available') failures.push('mediaTitle privacy');
  return failures;
}

export function validateLiveSnapshot(snapshot: PlayerDiagnosticsSnapshot): string[] {
  const failures: string[] = [];
  const duration = snapshot.fields.durationMs;
  const progress = snapshot.fields.progressPercent;
  if (!(duration.status === 'unavailable' || (duration.status === 'available' && duration.estimated))) failures.push('durationMs');
  if (!(progress.status === 'unavailable' || (progress.status === 'available' && progress.estimated))) failures.push('progressPercent');
  if (snapshot.fields.fileSizeBytes.status !== 'unavailable') failures.push('fileSizeBytes');
  return failures;
}
export interface ProbeSurfaceEvidence {
  destroyed: boolean; loaded: boolean; attached: boolean; firstFrame: boolean;
  oldId: string; newId: string; generation: number;
}
export function validateSurfaceRebuild(e: ProbeSurfaceEvidence): boolean {
  return e.destroyed && e.loaded && e.attached && e.firstFrame && e.oldId.length > 0 &&
    e.newId.length > 0 && e.oldId !== e.newId && e.generation === 2;
}
