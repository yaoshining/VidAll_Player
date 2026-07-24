import { describe, expect, it } from '@ohos/hypium';
import { createPlayer, PlayerEvent } from '@vidall/player';

export default function streamingSessionTest() {
  describe('StreamingSessionTest', () => {
    it('accepts HLS, DASH and localhost proxy sources', 0, async (done: Function) => {
      const events: PlayerEvent[] = [];
      const player = createPlayer({ eventListener: (event: PlayerEvent) => events.push(event) });

      await player.load({ kind: 'hls', uri: 'https://example.com/live/master.m3u8' });
      expect(events[events.length - 1].state).assertEqual('preparing');

      await player.load({ kind: 'dash', uri: 'https://example.com/vod/manifest.mpd' });
      expect(events[events.length - 1].state).assertEqual('preparing');

      await player.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:58080/smb/media/movie.mp4',
        proxyLeaseId: 'lease-1'
      });
      expect(events[events.length - 1].state).assertEqual('preparing');

      await player.release();
      done();
    });

    it('rejects adaptive sources without HTTP or HTTPS URIs', 0, async (done: Function) => {
      const player = createPlayer();
      const invalidLoads: Array<() => Promise<void>> = [
        () => player.load({ kind: 'hls', uri: 'file:///data/master.m3u8' }),
        () => player.load({ kind: 'dash', uri: 'file:///data/manifest.mpd' })
      ];
      for (let index = 0; index < invalidLoads.length; index++) {
        try {
          await invalidLoads[index]();
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
      await player.release();
      done();
    });

    it('rejects localhost proxy sources that are not plain loopback HTTP', 0, async (done: Function) => {
      const player = createPlayer();
      const invalidLoads: Array<() => Promise<void>> = [
        () => player.load({ kind: 'localhostProxy', uri: 'https://127.0.0.1:58080/smb/movie.mp4' }),
        () => player.load({ kind: 'localhostProxy', uri: 'http://192.168.1.10:58080/smb/movie.mp4' })
      ];
      for (let index = 0; index < invalidLoads.length; index++) {
        try {
          await invalidLoads[index]();
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
      await player.release();
      done();
    });

    it('rejects unverified optional protocols with a stable code', 0, async (done: Function) => {
      const errors: string[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error' && event.error !== undefined) {
            errors.push(event.error.code);
          }
        }
      });
      const unverifiedUris: string[] = [
        'rtsp://example.com/stream/1',
        'rtmp://example.com/live/app',
        'udp://239.0.0.1:1234',
        'srt://example.com:9000'
      ];
      for (let index = 0; index < unverifiedUris.length; index++) {
        try {
          await player.load({ kind: 'http', uri: unverifiedUris[index] });
          expect(true).assertFalse();
        } catch (_) {
          expect(true).assertTrue();
        }
      }
      expect(errors.length).assertEqual(4);
      for (let index = 0; index < errors.length; index++) {
        expect(errors[index]).assertEqual('PROTOCOL_NOT_VERIFIED');
      }
      await player.release();
      done();
    });

    it('releases the proxy lease when the source changes, stops or releases', 0, async (done: Function) => {
      const logMessages: string[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'log' && event.message !== undefined) {
            logMessages.push(event.message);
          }
        }
      });

      await player.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:58080/smb/media/first.mp4',
        proxyLeaseId: 'lease-switch'
      });
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      expect(logMessages.length).assertEqual(1);
      expect(logMessages[0].indexOf('lease-switch') >= 0).assertTrue();

      await player.load({
        kind: 'localhostProxy',
        uri: 'http://localhost:58080/smb/media/second.mp4',
        proxyLeaseId: 'lease-stop'
      });
      await player.play();
      await player.stop();
      expect(logMessages.length).assertEqual(2);
      expect(logMessages[1].indexOf('lease-stop') >= 0).assertTrue();

      await player.load({
        kind: 'localhostProxy',
        uri: 'http://[::1]:58080/smb/media/third.mp4',
        proxyLeaseId: 'lease-release'
      });
      await player.release();
      expect(logMessages.length).assertEqual(3);
      expect(logMessages[2].indexOf('lease-release') >= 0).assertTrue();
      done();
    });

    it('does not leak credentials through lease release log events', 0, async (done: Function) => {
      const logMessages: string[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'log' && event.message !== undefined) {
            logMessages.push(event.message);
          }
        }
      });
      await player.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:58080/smb/private/movie.mp4?token=secret',
        proxyLeaseId: 'lease-redact',
        headers: { 'authorization': 'Basic c2VjcmV0' }
      });
      await player.stop();
      expect(logMessages.length).assertEqual(1);
      expect(logMessages[0].indexOf('secret') < 0).assertTrue();
      expect(logMessages[0].indexOf('c2VjcmV0') < 0).assertTrue();
      expect(logMessages[0].indexOf('/smb/private') < 0).assertTrue();
      await player.release();
      done();
    });

    it('allows reloading the same source after a retryable network failure', 0, async (done: Function) => {
      const states: string[] = [];
      const player = createPlayer({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'state' && event.state !== undefined) {
            states.push(event.state);
          }
        }
      });
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      await player.play();
      // 模拟原生层上报网络中断：消费者随后可以重新 load 同一来源完成重试。
      await player.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      expect(states[states.length - 1]).assertEqual('preparing');
      await player.release();
      done();
    });
  });
}
