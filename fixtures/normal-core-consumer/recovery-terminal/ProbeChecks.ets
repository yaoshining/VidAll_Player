import { DiagnosticField, PlayerDiagnosticsSnapshot } from '@vidall/player';

export type ProbeProfile = 'hardware-first' | 'software-control';

export function initialMode(profile: ProbeProfile, generation: number): 'standard' | 'compatible' {
  if (profile !== 'hardware-first' && profile !== 'software-control') throw new Error('INVALID_PROBE_PROFILE');
  return profile === 'hardware-first' && generation === 1 ? 'standard' : 'compatible';
}

function actual(field: DiagnosticField<string>, source: string, value: string): boolean {
  return field.status === 'available' && field.estimated === false && field.source === source && field.value === value;
}

function live(snapshot: PlayerDiagnosticsSnapshot): boolean {
  return snapshot.schemaVersion === 1 && snapshot.freshness !== 'cached-terminal';
}

export function requireHardware(snapshot: PlayerDiagnosticsSnapshot): void {
  if (!live(snapshot) || !actual(snapshot.fields.renderBackend, 'session.actual-render-backend', 'vulkan') ||
    !actual(snapshot.fields.hardwareDecoder, 'hwdec-current', 'ohcodec')) throw new Error('HARDWARE_PATH_REQUIRED');
}

export function requireSoftwareDecode(snapshot: PlayerDiagnosticsSnapshot): void {
  if (!live(snapshot) || !actual(snapshot.fields.hardwareDecoder, 'hwdec-current', 'no')) {
    throw new Error('SOFTWARE_DECODE_REQUIRED');
  }
}

export function requireSoftware(snapshot: PlayerDiagnosticsSnapshot): void {
  if (!live(snapshot) || !actual(snapshot.fields.renderBackend, 'session.actual-render-backend', 'software') ||
    !actual(snapshot.fields.hardwareDecoder, 'hwdec-current', 'no')) throw new Error('SOFTWARE_PATH_REQUIRED');
}
