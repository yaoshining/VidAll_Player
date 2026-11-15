import { capturePlayerRuntimeGeneration } from './runtime';
import { PlayerOptions } from './types';
import { VidAllPlayer } from './playerContract';
import { PlayerSession } from '../internal/playerSession';

export { VidAllPlayer } from './playerContract';

export function createPlayer(options?: PlayerOptions): VidAllPlayer {
  capturePlayerRuntimeGeneration(options?.playbackMode === 'compatible');
  return new PlayerSession(options);
}
