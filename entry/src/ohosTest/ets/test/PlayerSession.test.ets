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

    it('accepts credential-free SMB syntax but refuses unavailable native support', 0, async (done: Function) => {
      const errors: PlayerError[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error' && event.error !== undefined) {
            errors.push(event.error);
          }
        }
      });

      try {
        await player.load({ kind: 'smb', uri: 'smb://files.example/media/video.mkv' });
        expect(true).assertFalse();
      } catch (_) {
        expect(errors.length).assertEqual(1);
        expect(errors[0].code).assertEqual('PROTOCOL_NOT_AVAILABLE');
        expect(errors[0].message.indexOf('files.example') < 0).assertTrue();
      }
      await player.release();
      done();
    });

    it('rejects malformed SMB paths before checking native support', 0, async (done: Function) => {
      const invalidUris: string[] = [
        'smb://:445/media/video.mkv',
        'smb://files.example/',
        'smb://files.example/media/../video.mkv',
        'smb://files.example/media/%2e%2e/video.mkv'
      ];

      for (let index = 0; index < invalidUris.length; index++) {
        const errors: PlayerError[] = [];
        const player = createPlayer({
          eventListener: (event: PlayerEvent) => {
            if (event.type === 'error' && event.error !== undefined) {
              errors.push(event.error);
            }
          }
        });
        try {
          await player.load({ kind: 'smb', uri: invalidUris[index] });
          expect(true).assertFalse();
        } catch (_) {
          expect(errors.length).assertEqual(1);
          expect(errors[0].code).assertEqual('INVALID_SMB_URI');
        }
        await player.release();
      }
      done();
    });

    it('rejects SMB userinfo before checking native support', 0, async (done: Function) => {
      const errors: PlayerError[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error' && event.error !== undefined) {
            errors.push(event.error);
          }
        }
      });

      try {
        await player.load({ kind: 'smb', uri: 'smb://user:secret@files.example/media/video.mkv' });
        expect(true).assertFalse();
      } catch (_) {
        expect(errors.length).assertEqual(1);
        expect(errors[0].code).assertEqual('URL_USERINFO_FORBIDDEN');
        expect(errors[0].message.indexOf('secret') < 0).assertTrue();
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
      await player.setRate(0.5);
      await player.setVolume(0);
      await player.setVolume(100);
      await player.mute(true);
      await player.mute(false);
      await player.selectTrack('audio', null);
      await player.setSubtitleDelay(-250);
      await player.release();
      done();
    });

    it('announces external subtitles as renderable tracks and updates selection', 0, async (done: Function) => {
      const trackEvents: PlayerEvent[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'tracks') {
            trackEvents.push(event);
          }
        }
      });

      await player.load({
        kind: 'https',
        uri: 'https://example.com/video.mp4',
        externalSubtitles: [{ uri: 'https://example.com/subtitle.srt', title: 'Chinese', format: 'srt' }]
      });
      await player.selectTrack('subtitle', 1);
      await player.selectTrack('subtitle', null);

      expect(trackEvents.length).assertEqual(3);
      expect(trackEvents[0].tracks![0].title).assertEqual('Chinese');
      expect(trackEvents[0].tracks![0].recognitionStatus).assertEqual('renderable');
      expect(trackEvents[1].tracks![0].selected).assertTrue();
      expect(trackEvents[2].tracks![0].selected).assertFalse();
      await player.release();
      done();
    });

    it('emitted tracks snapshots are immutable across later selection changes', 0, async (done: Function) => {
      const trackEvents: PlayerEvent[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'tracks') {
            trackEvents.push(event);
          }
        }
      });

      await player.load({
        kind: 'https',
        uri: 'https://example.com/video.mp4',
        externalSubtitles: [{ uri: 'https://example.com/subtitle.srt', title: 'Chinese', format: 'srt' }]
      });
      expect(trackEvents.length).assertEqual(1);
      const firstSnapshot = trackEvents[0].tracks!;
      expect(firstSnapshot[0].selected).assertFalse();

      await player.selectTrack('subtitle', 1);
      // 回归断言：selectTrack 只能改当前轨道状态，不得回溯污染早先投递的快照。
      expect(trackEvents[1].tracks![0].selected).assertTrue();
      expect(firstSnapshot[0].selected).assertFalse();

      await player.selectTrack('subtitle', null);
      expect(firstSnapshot[0].selected).assertFalse();
      await player.release();
      done();
    });

    it('loads and selects external audio while rejecting invalid audio URIs', 0, async (done: Function) => {
      const trackEvents: PlayerEvent[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'tracks') {
            trackEvents.push(event);
          }
        }
      });
      await player.load({
        kind: 'https',
        uri: 'https://example.com/video.mp4',
        externalAudio: [{ uri: 'https://example.com/audio.aac', title: 'Chinese', language: 'zh' }]
      });
      await player.selectTrack('audio', 1);
      expect(trackEvents.length).assertEqual(2);
      expect(trackEvents[0].tracks![0].kind).assertEqual('audio');
      expect(trackEvents[0].tracks![0].language).assertEqual('zh');
      expect(trackEvents[1].tracks![0].selected).assertTrue();
      await player.release();

      const invalidPlayer = createPlayer();
      try {
        await invalidPlayer.load({
          kind: 'https',
          uri: 'https://example.com/video.mp4',
          externalAudio: [{ uri: '' }]
        });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await invalidPlayer.release();
      done();
    });

    it('rejects an invalid external audio URI added after load', 0, async (done: Function) => {
      const player = createPlayer();
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      try {
        await player.addExternalAudio({ uri: '' });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await player.release();
      done();
    });

    it('emits structured log payloads while preserving the legacy message', 0, async (done: Function) => {
      const logEvents: PlayerEvent[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'log') {
            logEvents.push(event);
          }
        }
      });
      await player.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:18080/smb/video.mp4',
        proxyLeaseId: 'lease-1'
      });
      await player.release();
      expect(logEvents.length).assertEqual(1);
      expect(logEvents[0].log!.level).assertEqual('info');
      expect(logEvents[0].log!.module).assertEqual('player-session');
      expect(logEvents[0].log!.message).assertEqual(logEvents[0].message!);
      done();
    });

    it('adds supported external subtitles and rejects invalid tracks and formats', 0, async (done: Function) => {
      const player = createPlayer();
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      await player.addExternalSubtitle({ uri: 'https://example.com/subtitle.ass', format: 'ass' });

      const invalidCommands: Array<() => Promise<void>> = [
        () => player.selectTrack('subtitle', 2),
        () => player.selectTrack('audio', 1),
        () => player.addExternalSubtitle({ uri: 'https://example.com/subtitle.txt', format: 'txt' as 'srt' })
      ];
      for (let index = 0; index < invalidCommands.length; index++) {
        try {
          await invalidCommands[index]();
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
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
        () => player.setRate(Number.POSITIVE_INFINITY),
        () => player.setRate(0),
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
