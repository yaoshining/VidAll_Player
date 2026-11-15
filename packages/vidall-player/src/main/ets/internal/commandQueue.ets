import { lifecycleFailure, PlayerFailure } from './playerFailure';

class PendingCommand {
  readonly resolve: () => void;
  readonly reject: (error: Error | PlayerFailure) => void;
  constructor(resolve: () => void, reject: (error: Error | PlayerFailure) => void) {
    this.resolve = resolve;
    this.reject = reject;
  }
}

export class CommandQueue {
  private tail: Promise<void> = Promise.resolve();
  private closedError?: Error | PlayerFailure;
  private readonly pending: Set<PendingCommand> = new Set();

  enqueue(operation: () => Promise<void>): Promise<void> {
    if (this.closedError !== undefined) return Promise.reject(this.closedError);
    if (this.pending.size >= 64) {
      return Promise.reject(lifecycleFailure('COMMAND_QUEUE_FULL', '播放器操作过多，请稍后重试。'));
    }
    return new Promise<void>((resolve, reject) => {
      const command = new PendingCommand(resolve, reject);
      this.pending.add(command);
      const next = this.tail.then(async () => {
        if (this.closedError !== undefined) return;
        try {
          await operation();
          if (this.pending.delete(command)) command.resolve();
        } catch (error) {
          if (this.pending.delete(command)) {
            command.reject(error instanceof Error ? error : new Error('PLAYER_COMMAND_FAILED'));
          }
        }
      });
      this.tail = next;
    });
  }

  close(error: Error | PlayerFailure = lifecycleFailure('RELEASED', 'Player session has been released.')): void {
    if (this.closedError !== undefined) return;
    this.closedError = error;
    // 只结束调用方等待；原生在途任务及其资源仍由原生命周期持有。
    this.pending.forEach((command: PendingCommand) => command.reject(error));
    this.pending.clear();
  }
}
