import { PlayerEvent, PlayerState } from '../public/types';
import { lifecycleFailure } from './playerFailure';

export type ReleasePhase = 'open' | 'closing' | 'closed';
type EventListener = (event: PlayerEvent) => void;

export class SessionStateMachine {
  private state: PlayerState = 'idle';
  private phase: ReleasePhase = 'open';
  private sequence: number = 0;
  private eventEpoch: number = 0;
  private surfaceGeneration?: number;
  private nativeSequence: number = 0;
  private readonly listeners: EventListener[] = [];

  getState(): PlayerState { return this.state; }
  getReleasePhase(): ReleasePhase { return this.phase; }

  advanceEventEpoch(): number {
    this.eventEpoch += 1;
    this.nativeSequence = 0;
    return this.eventEpoch;
  }

  setSurfaceGeneration(generation: number | undefined): void {
    this.surfaceGeneration = generation;
  }

  matchesNativeContext(eventEpoch: number, surfaceGeneration: number): boolean {
    return this.phase === 'open' && eventEpoch === this.eventEpoch && surfaceGeneration === this.surfaceGeneration;
  }

  acceptNativeSequence(eventEpoch: number, sequence: number): boolean {
    if (eventEpoch !== this.eventEpoch || sequence <= this.nativeSequence) {
      return false;
    }
    this.nativeSequence = sequence;
    return true;
  }

  emitIncoming(event: PlayerEvent): boolean {
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
    if (this.phase === 'closed' && event.type !== 'closed') { return; }
    this.sequence += 1;
    event.sequence = this.sequence;
    event.eventEpoch = this.eventEpoch;
    const listeners = this.listeners.slice();
    for (let index = 0; index < listeners.length; index++) { listeners[index](event); }
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
