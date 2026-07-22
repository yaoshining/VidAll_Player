import { PlayerEvent, PlayerState } from '../public/types';
import { lifecycleFailure } from './playerFailure';

export type ReleasePhase = 'open' | 'closing' | 'closed';
type EventListener = (event: PlayerEvent) => void;

export class SessionStateMachine {
  private state: PlayerState = 'idle';
  private phase: ReleasePhase = 'open';
  private sequence: number = 0;
  private readonly listeners: EventListener[] = [];

  getState(): PlayerState { return this.state; }
  getReleasePhase(): ReleasePhase { return this.phase; }

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
