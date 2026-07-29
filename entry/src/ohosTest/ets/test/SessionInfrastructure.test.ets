import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerEvent } from '@vidall/player';
import { ApiLevelProvider, CapabilityProbe } from '@vidall/player/src/internal/capabilities';
import { CommandQueue } from '@vidall/player/src/internal/commandQueue';
import { SessionStateMachine } from '@vidall/player/src/internal/stateMachine';
import { XComponentSurfaceAdapter, PlayerSurfaceTarget } from '@vidall/player/src/xcomponent/surfaceAdapter';

class TestSurfaceTarget implements PlayerSurfaceTarget {
  attached: number = 0;

  async attachSurface(): Promise<void> { this.attached += 1; }
  async resizeSurface(): Promise<void> {}
  async detachSurface(): Promise<void> {}
}

class Api18Provider implements ApiLevelProvider {
  getApiLevel(): number { return 18; }
}

export default function sessionInfrastructureTest() {
  describe('SessionInfrastructureTest', () => {
    it('increments source epochs and discards stale epoch and surface events', 0, async (done: Function) => {
      const playerEvents: PlayerEvent[] = [];
      const player = createPlayer({ eventListener: (event: PlayerEvent) => playerEvents.push(event) });
      await player.load({ kind: 'https', uri: 'https://example.com/first.mp4' });
      const firstPlayerEpoch = playerEvents[playerEvents.length - 1].eventEpoch ?? 0;
      expect(firstPlayerEpoch).assertEqual(1);
      await player.load({ kind: 'https', uri: 'https://example.com/second.mp4' });
      const secondPlayerEpoch = playerEvents[playerEvents.length - 1].eventEpoch ?? 0;
      expect(secondPlayerEpoch).assertEqual(firstPlayerEpoch + 1);
      await player.release();

      const events: PlayerEvent[] = [];
      const stateMachine = new SessionStateMachine();
      stateMachine.subscribe((event: PlayerEvent) => events.push(event));

      const firstEpoch = stateMachine.advanceEventEpoch();
      stateMachine.setSurfaceGeneration(2);
      expect(stateMachine.emitIncoming({ type: 'firstFrame', sequence: 0, eventEpoch: firstEpoch })).assertFalse();
      expect(stateMachine.emitIncoming({ type: 'firstFrame', sequence: 0, eventEpoch: firstEpoch, surfaceGeneration: 1 })).assertFalse();
      expect(stateMachine.emitIncoming({ type: 'firstFrame', sequence: 0, eventEpoch: firstEpoch, surfaceGeneration: 2 })).assertTrue();

      const secondEpoch = stateMachine.advanceEventEpoch();
      expect(secondEpoch).assertEqual(firstEpoch + 1);
      expect(stateMachine.emitIncoming({ type: 'position', sequence: 0, eventEpoch: firstEpoch, positionMs: 1 })).assertFalse();
      expect(stateMachine.emitIncoming({ type: 'position', sequence: 0, eventEpoch: secondEpoch, positionMs: 2 })).assertTrue();
      expect(events.length).assertEqual(2);
      expect(events[0].eventEpoch).assertEqual(firstEpoch);
      expect(events[1].eventEpoch).assertEqual(secondEpoch);
      expect(events[1].sequence > events[0].sequence).assertTrue();
      done();
    });

    it('does not execute queued commands after close', 0, async (done: Function) => {
      const queue = new CommandQueue();
      const order: string[] = [];
      let unblockFirst: () => void = () => {};
      let signalFirstStarted: () => void = () => {};
      const firstStarted = new Promise<void>((resolve) => { signalFirstStarted = resolve; });
      const first = queue.enqueue(() => new Promise<void>((resolve) => {
        order.push('first');
        signalFirstStarted();
        unblockFirst = resolve;
      }));
      const firstResult = first.then(() => true, () => false);
      await firstStarted;

      const second = queue.enqueue(() => {
        order.push('second');
        return Promise.resolve();
      });
      const secondResult = second.then(() => true, () => false);
      queue.close();
      unblockFirst();

      expect(await firstResult).assertTrue();
      expect(await secondResult).assertFalse();
      expect(order.length).assertEqual(1);
      expect(order[0]).assertEqual('first');
      done();
    });

    it('validates surface dimensions before invoking the target', 0, async (done: Function) => {
      const target = new TestSurfaceTarget();
      const adapter = new XComponentSurfaceAdapter('player', target);
      try {
        await adapter.onLoad(0, 1080);
        expect(true).assertFalse();
      } catch (_) {
        expect(target.attached).assertEqual(0);
      }
      await adapter.onLoad(1920, 1080);
      expect(target.attached).assertEqual(1);
      done();
    });

    it('records explicit API 15 through 18 fallback decisions', 0, () => {
      const probe = new CapabilityProbe(new Api18Provider());
      const decision = probe.evaluate('advanced-renderer', 19, 'software-fallback');
      expect(decision.currentApi).assertEqual(18);
      expect(decision.outcome).assertEqual('software-fallback');
    });
  });
}
