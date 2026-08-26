import { PlayerError } from '../public/types';

export class PlayerFailure extends Error {
  readonly playerError: PlayerError;

  constructor(playerError: PlayerError) {
    super(playerError.message);
    this.playerError = playerError;
  }
}

export function lifecycleFailure(code: string, message: string): PlayerFailure {
  return new PlayerFailure({
    domain: 'lifecycle',
    code,
    message,
    retryable: false,
    context: {}
  });
}
