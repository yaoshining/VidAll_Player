export const BUNDLE: string = 'com.yaoshining.vidalldeviceprobe';
export interface JournalPort { mkdirExclusive(nonce: string): void; append(line: string): void; now(): number; pid(): number; }
export interface SessionEvent { schemaVersion: number; unsignedHapSHA256: string; nonce: string; bundle: string; pid: number; startedAtMs: number; elapsedMs: number; seq: number; event: string; cycle: number; value: string; }
export function validateLaunch(nonce: string, mode: string, unsignedSHA: string): void {
  if (!/^[0-9a-f]{32}$/.test(nonce) || mode !== 'normal-local-smoke' || !/^[0-9a-f]{64}$/.test(unsignedSHA)) throw new Error('INVALID_LAUNCH');
}
export class SessionJournal {
  private seq: number = 0;
  private unsignedSHA: string = '';
  private started: number = 0;
  private initialized: boolean = false;
  private port: JournalPort;
  private nonce: string;
  constructor(port: JournalPort, nonce: string) { this.port = port; this.nonce = nonce; }
  start(mode: string, unsignedSHA: string): void {
    validateLaunch(this.nonce, mode, unsignedSHA);
    if (this.initialized) throw new Error('NONCE_REUSE');
    this.port.mkdirExclusive(this.nonce); this.unsignedSHA = unsignedSHA; this.started = this.port.now(); this.initialized = true;
    this.record('session-start', 0, JSON.stringify({ mode, expectedUnsignedHapSHA256: unsignedSHA, identityEvidence: 'launch-statement-only' }));
  }
  record(event: string, cycle: number, value: string): void {
    if (!this.initialized) throw new Error('SESSION_NOT_STARTED');
    const row: SessionEvent = { schemaVersion: 1, unsignedHapSHA256: this.unsignedSHA, nonce: this.nonce, bundle: BUNDLE, pid: this.port.pid(), startedAtMs: this.started, elapsedMs: this.port.now() - this.started, seq: ++this.seq, event, cycle, value };
    this.port.append(JSON.stringify(row) + '\n');
  }
}
