import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerError, PlayerEvent, VidAllPlayer } from '@vidall/player';

interface PlayerFailureLike {
  playerError?: PlayerError;
}

async function expectFailure(operation: () => Promise<void>, code: string): Promise<void> {
  let error: Object | undefined = undefined;
  try {
    await operation();
  } catch (caught) {
    error = caught as Object;
  }
  expect(error !== undefined).assertTrue();
  expect((error as PlayerFailureLike).playerError?.code).assertEqual(code);
}

export default function playerLifecycleTest(): void {
  describe('PlayerLifecycleTest', () => {
    it('keeps idle stop and repeated release idempotent, then rejects controls', 0, async (done: Function) => {
      const player: VidAllPlayer = createPlayer();
      await player.stop();
      let closedEvents = 0;
      const unsubscribe = player.subscribe((event: PlayerEvent): void => {
        if (event.type === 'closed') {
          closedEvents += 1;
        }
      });
      await player.release();
      await player.release();
      unsubscribe();
      expect(closedEvents).assertEqual(1);
      await expectFailure(() => player.stop(), 'RELEASED');
      await expectFailure(() => player.play(), 'RELEASED');
      await expectFailure(() => player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' }), 'RELEASED');
      await expectFailure(() => player.attachSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 }), 'RELEASED');
      await expectFailure(() => player.resizeSurface({ componentId: 'surface', generation: 1, width: 1280, height: 720 }), 'RELEASED');
      await expectFailure(() => player.detachSurface(1), 'RELEASED');
      done();
    });

    it('closes subscriptions and allows a fresh session after release', 0, async (done: Function) => {
      const released: VidAllPlayer = createPlayer();
      let delivered = 0;
      released.subscribe((_event: PlayerEvent): void => {
        delivered += 1;
      });
      const beforeRelease = delivered;
      await released.release();
      expect(delivered).assertEqual(beforeRelease + 2);

      const afterRelease = delivered;
      const fresh: VidAllPlayer = createPlayer();
      await fresh.stop();
      await fresh.release();
      expect(delivered).assertEqual(afterRelease);
      done();
    });
  });
}
