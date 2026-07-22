import { lifecycleFailure } from './playerFailure';

export class CommandQueue {
  private tail: Promise<void> = Promise.resolve();
  private accepting: boolean = true;

  enqueue(operation: () => Promise<void>): Promise<void> {
    if (!this.accepting) {
      return Promise.reject(lifecycleFailure('SESSION_RELEASED', 'Player session has been released.'));
    }
    const next = this.tail.then(() => {
      if (!this.accepting) {
        throw lifecycleFailure('SESSION_RELEASED', 'Player session has been released.');
      }
      return operation();
    });
    this.tail = next.catch(() => {});
    return next;
  }

  close(): void {
    this.accepting = false;
  }
}
