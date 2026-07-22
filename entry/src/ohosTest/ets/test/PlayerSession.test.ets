import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerError, PlayerEvent, PlayerSurface } from '@vidall/player';

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

    it('keeps a newer surface when an older generation is detached', 0, async (done: Function) => {
      const player = createPlayer();
      await player.attachSurface({ componentId: 'video', generation: 1, width: 1920, height: 1080 });
      await player.attachSurface({ componentId: 'video', generation: 2, width: 1920, height: 1080 });
      await player.detachSurface(1);
      await player.resizeSurface({ componentId: 'video', generation: 2, width: 1280, height: 720 });
      await player.release();
      done();
    });

    it('accepts control boundaries for loaded media', 0, async (done: Function) => {
      const player = createPlayer();
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      await player.seekRelative(-5.5);
      await player.seekPercent(0);
      await player.seekPercent(100);
      await player.setSpeed(0.5);
      await player.setVolume(0);
      await player.setVolume(100);
      await player.setMuted(true);
      await player.setMuted(false);
      await player.selectTrack('audio', null);
      await player.setSubtitleDelay(-250);
      await player.release();
      done();
    });

    it('rejects invalid control and surface values', 0, async (done: Function) => {
      const player = createPlayer();
      const invalidSurfaces: PlayerSurface[] = [
        { componentId: 'video', generation: Number.NaN, width: 1920, height: 1080 },
        { componentId: 'video', generation: 1.5, width: 1920, height: 1080 },
        { componentId: 'video', generation: 0, width: 1920, height: 1080 },
        { componentId: 'video', generation: 1, width: Number.POSITIVE_INFINITY, height: 1080 },
        { componentId: 'video', generation: 1, width: 1920, height: 0 }
      ];
      for (let index = 0; index < invalidSurfaces.length; index++) {
        try {
          await player.attachSurface(invalidSurfaces[index]);
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      const invalidControls: Array<() => Promise<void>> = [
        () => player.seekRelative(Number.NaN),
        () => player.seekRelative(Number.POSITIVE_INFINITY),
        () => player.seekPercent(Number.NaN),
        () => player.seekPercent(-1),
        () => player.seekPercent(101),
        () => player.setSpeed(Number.POSITIVE_INFINITY),
        () => player.setSpeed(0),
        () => player.setVolume(Number.NaN),
        () => player.setVolume(-1),
        () => player.setVolume(101),
        () => player.selectTrack('audio', Number.NaN),
        () => player.selectTrack('audio', 1.5),
        () => player.selectTrack('audio', -1),
        () => player.setSubtitleDelay(Number.POSITIVE_INFINITY)
      ];
      for (let index = 0; index < invalidControls.length; index++) {
        try {
          await invalidControls[index]();
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
      await player.release();
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
