import { assertPlayerRuntimeReady } from './runtime';
import { PlayerOptions } from './types';
import { VidAllPlayer } from './playerContract';
import { PlayerSession } from '../internal/playerSession';

export { VidAllPlayer } from './playerContract';

export function createPlayer(options?: PlayerOptions): VidAllPlayer {
  assertPlayerRuntimeReady();
  return new PlayerSession(options);
}
