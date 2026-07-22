import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerError, PlayerEvent } from '@vidall/player';

export default function playerSessionTest() {
  describe('PlayerSessionTest', () => {
    it('load reports a structured validation error without credentials', 0, async (done: Function) => {
      const errors: PlayerError[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error' && event.error !== undefined) {
            errors.push(event.error);
          }
        }
      });

      try {
        await player.load({ kind: 'https', uri: 'https://user:secret@example.com/video.mp4' });
        expect(true).assertFalse();
      } catch (_) {
        expect(errors.length).assertEqual(1);
        expect(errors[0].code).assertEqual('URL_USERINFO_FORBIDDEN');
        expect(errors[0].message.indexOf('secret') < 0).assertTrue();
      }
      await player.release();
      done();
    });

    it('rejects a localhost proxy that targets a remote host', 0, async (done: Function) => {
      const player = createPlayer();
      try {
        await player.load({ kind: 'localhostProxy', uri: 'http://localhost.evil.com/video.mp4' });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await player.release();
      done();
    });

    it('emits ordered state and closed events for a normal session', 0, async (done: Function) => {
      const events: PlayerEvent[] = [];
      const player = createPlayer({ eventListener: (event: PlayerEvent) => events.push(event) });

      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      await player.play();
      await player.pause();
      await player.stop();
      await player.release();

      expect(events.length).assertEqual(6);
      expect(events[0].state).assertEqual('preparing');
      expect(events[1].state).assertEqual('playing');
      expect(events[2].state).assertEqual('paused');
      expect(events[3].state).assertEqual('idle');
      expect(events[4].state).assertEqual('released');
      expect(events[5].type).assertEqual('closed');
      for (let index = 0; index < events.length; index++) {
        expect(events[index].sequence).assertEqual(index + 1);
      }
      done();
    });

    it('rejects invalid surfaces and commands issued after release', 0, async (done: Function) => {
      const player = createPlayer();
      try {
        await player.attachSurface({ componentId: '', generation: 1, width: 1920, height: 1080 });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await player.release();
      try {
        await player.play();
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      done();
    });
  });
}
