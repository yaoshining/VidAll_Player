import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerError, PlayerSurface, VidAllPlayer } from '@vidall/player';

interface PlayerFailureLike {
  playerError?: PlayerError;
}

function assertReleased(error: Object | undefined): void {
  const failure = error as PlayerFailureLike;
  expect(failure.playerError?.code).assertEqual('RELEASED');
}

async function expectReleased(operation: () => Promise<void>): Promise<void> {
  let error: Object | undefined = undefined;
  try {
    await operation();
  } catch (caught) {
    error = caught as Object;
  }
  expect(error !== undefined).assertTrue();
  assertReleased(error);
}

export default function publicImportTest(): void {
  describe('PublicImportTest', () => {
    it('imports only the public entry and creates/releases an ARM64 native session', 0, async (done: Function) => {
      const player: VidAllPlayer = createPlayer();
      const surface: PlayerSurface = { componentId: 'fixture', generation: 1, width: 1920, height: 1080 };
      expect(typeof player.release).assertEqual('function');
      await player.release();
      await player.release();
      await expectReleased(() => player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' }));
      await expectReleased(() => player.play());
      await expectReleased(() => player.attachSurface(surface));
      done();
    });
  });
}
