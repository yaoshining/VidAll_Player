import { PlayerOptions } from './types';
import { VidAllPlayer } from './playerContract';
import { PlayerSession } from '../internal/playerSession';

export { VidAllPlayer } from './playerContract';

export function createPlayer(options?: PlayerOptions): VidAllPlayer {
  return new PlayerSession(options);
}
