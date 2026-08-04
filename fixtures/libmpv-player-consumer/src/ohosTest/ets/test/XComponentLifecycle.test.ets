import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerError, PlayerSurface, VidAllPlayer, VidAllPlayerSurfaceTarget, XComponentSurfaceAdapter } from '@vidall/player';

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

export default function xcomponentLifecycleTest(): void {
  describe('XComponentLifecycleTest', () => {
    it('rejects load and play before an XComponent surface attaches', 0, async (done: Function) => {
      const player: VidAllPlayer = createPlayer();
      await expectFailure(() => player.load({ kind: 'https', uri: 'https://fixture.invalid/media.mp4' }), 'SURFACE_UNAVAILABLE');
      await expectFailure(() => player.play(), 'INVALID_STATE');
      await player.release();
      done();
    });

    it('rejects zero-sized and stale XComponent surface generations', 0, async (done: Function) => {
      const player: VidAllPlayer = createPlayer();
      const invalid: PlayerSurface = { componentId: 'not-a-surface-id', generation: 1, width: 0, height: 720 };
      await expectFailure(() => player.attachSurface(invalid), 'INVALID_SURFACE');
      await expectFailure(() => player.resizeSurface({ componentId: 'not-a-surface-id', generation: 2, width: 1280, height: 720 }), 'INVALID_SURFACE_GENERATION');
      await player.release();
      done();
    });

    it('validates adapter IDs and dimensions before forwarding XComponent work', 0, async (done: Function) => {
      const player: VidAllPlayer = createPlayer();
      const adapter = new XComponentSurfaceAdapter(new VidAllPlayerSurfaceTarget(player));
      await expectFailure(() => adapter.onLoad('', 1280, 720), 'INVALID_SURFACE');
      await expectFailure(() => adapter.onLoad('surface', 0, 720), 'INVALID_SURFACE');
      await expectFailure(() => adapter.onSizeChange(1280, Number.NaN), 'INVALID_SURFACE');
      await player.release();
      done();
    });
  });
}
