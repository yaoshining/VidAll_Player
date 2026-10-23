import { PlayerEvent, PlayerState, PlayerError } from '../public/types';
import { lifecycleFailure } from './playerFailure';

export type ReleasePhase = 'open' | 'closing' | 'closed';
type EventListener = (event: PlayerEvent) => void;

export class SessionStateMachine {
  private state: PlayerState = 'idle';
  private terminal: boolean = false;
  private phase: ReleasePhase = 'open';
  private sequence: number = 0;
  private eventEpoch: number = 0;
  private surfaceGeneration?: number;
  private nativeSequence: number = 0;
  private readonly listeners: EventListener[] = [];

  getState(): PlayerState { return this.state; }
  getReleasePhase(): ReleasePhase { return this.phase; }

  advanceEventEpoch(): number {
    if (this.terminal) return this.eventEpoch;
    this.eventEpoch += 1;
    this.nativeSequence = 0;
    return this.eventEpoch;
  }

  setSurfaceGeneration(generation: number | undefined): void {
    if (this.terminal) return;
    this.surfaceGeneration = generation;
  }

  matchesNativeContext(eventEpoch: number, surfaceGeneration: number): boolean {
    return !this.terminal && this.phase === 'open' && eventEpoch === this.eventEpoch && surfaceGeneration === this.surfaceGeneration;
  }

  acceptNativeSequence(eventEpoch: number, sequence: number): boolean {
    if (this.terminal) return false;
    if (eventEpoch !== this.eventEpoch || sequence <= this.nativeSequence) {
      return false;
    }
    this.nativeSequence = sequence;
    return true;
  }

  emitIncoming(event: PlayerEvent): boolean {
    if (this.terminal) return false;
    if (this.phase === 'closed' || event.eventEpoch !== this.eventEpoch ||
      (event.type === 'firstFrame' && event.surfaceGeneration === undefined) ||
      (event.surfaceGeneration !== undefined && event.surfaceGeneration !== this.surfaceGeneration)) {
      return false;
    }
    this.emit(event);
    return true;
  }

  subscribe(listener: EventListener): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) { this.listeners.splice(index, 1); }
    };
  }

  transition(next: PlayerState): void {
    if (this.terminal) return;
    if (this.state === next) { return; }
    if (!this.canTransition(next)) {
      throw lifecycleFailure('INVALID_STATE', `Cannot transition from ${this.state} to ${next}.`);
    }
    this.state = next;
    const event: PlayerEvent = { type: 'state', sequence: 0, state: next };
    this.emit(event);
  }

  release(): boolean {
    if (this.phase !== 'open') { return false; }
    this.phase = 'closing';
    this.transition('released');
    this.phase = 'closed';
    const event: PlayerEvent = { type: 'closed', sequence: 0 };
    this.emit(event);
    this.listeners.splice(0, this.listeners.length);
    return true;
  }

  emit(event: PlayerEvent): void {
    if (this.terminal) return;
    if (this.phase === 'closed' && event.type !== 'closed') { return; }
    this.sequence += 1;
    event.sequence = this.sequence;
    event.eventEpoch = this.eventEpoch;
    const listeners = this.listeners.slice();
    for (let index = 0; index < listeners.length; index++) { listeners[index](event); }
  }

  enterTerminal(): void {
    if (this.terminal || this.phase === 'closed') return;
    this.terminal = true;
    this.state = 'error';
    const error: PlayerError = { domain: 'native', code: 'PLAYER_TERMINAL',
      message: '播放器无法安全继续，请重新打开应用。', retryable: false, context: {} };
    const events: PlayerEvent[] = [
      { type: 'state', sequence: 0, state: 'error' },
      { type: 'error', sequence: 0, error }
    ];
    for (const event of events) {
      event.sequence = ++this.sequence; event.eventEpoch = this.eventEpoch;
      for (const listener of this.listeners.slice()) {
        try { listener(event); } catch (_) { console.error('VidAllPlayer: terminal event listener failed'); }
      }
    }
  }

  private canTransition(next: PlayerState): boolean {
    if (next === 'released') { return this.state !== 'released'; }
    if (this.state === 'idle') { return next === 'preparing' || next === 'error'; }
    if (this.state === 'preparing') { return next === 'playing' || next === 'error' || next === 'idle'; }
    if (this.state === 'playing' || this.state === 'paused') { return next === 'playing' || next === 'paused' || next === 'buffering' || next === 'completed' || next === 'error' || next === 'idle'; }
    if (this.state === 'buffering') { return next === 'playing' || next === 'paused' || next === 'error' || next === 'idle'; }
    if (this.state === 'completed' || this.state === 'error') { return next === 'preparing' || next === 'idle'; }
    return false;
  }
}
