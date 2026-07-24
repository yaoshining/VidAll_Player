import { describe, expect, it } from '@ohos/hypium';
import { PlayerEvent } from '@vidall/player';
import { PlayerSession } from '@vidall/player/src/internal/playerSession';
import { ProxyLeaseRegistry } from '@vidall/player/src/internal/proxyLeaseRegistry';
import { classifyNetworkFailure } from '@vidall/player/src/internal/networkRecovery';

export default function streamingInternalsTest() {
  describe('StreamingInternalsTest', () => {
    it('reports cache buffering transitions and restores the previous state', 0, async (done: Function) => {
      const events: PlayerEvent[] = [];
      const session = new PlayerSession({ eventListener: (event: PlayerEvent) => events.push(event) });
      await session.load({ kind: 'hls', uri: 'https://example.com/live/master.m3u8' });
      await session.play();

      session.reportBuffering(true, 25);
      let bufferingEvents = events.filter((event: PlayerEvent) => event.type === 'buffering');
      expect(bufferingEvents.length).assertEqual(1);
      expect(bufferingEvents[0].paused).assertTrue();
      expect(bufferingEvents[0].percent).assertEqual(25);
      expect(events[events.length - 2].state).assertEqual('buffering');

      session.reportBuffering(true, 60);
      bufferingEvents = events.filter((event: PlayerEvent) => event.type === 'buffering');
      expect(bufferingEvents.length).assertEqual(2);
      expect(bufferingEvents[1].percent).assertEqual(60);

      session.reportBuffering(false);
      bufferingEvents = events.filter((event: PlayerEvent) => event.type === 'buffering');
      expect(bufferingEvents.length).assertEqual(3);
      expect(bufferingEvents[2].paused).assertFalse();
      expect(events[events.length - 2].state).assertEqual('playing');

      await session.release();
      done();
    });

    it('restores paused state after buffering and ignores reports after release', 0, async (done: Function) => {
      const states: string[] = [];
      const session = new PlayerSession({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'state' && event.state !== undefined) {
            states.push(event.state);
          }
        }
      });
      await session.load({ kind: 'dash', uri: 'https://example.com/vod/manifest.mpd' });
      await session.play();
      await session.pause();
      session.reportBuffering(true, 10);
      session.reportBuffering(false);
      expect(states[states.length - 1]).assertEqual('paused');

      await session.release();
      const eventCount = states.length;
      session.reportBuffering(true, 99);
      expect(states.length).assertEqual(eventCount);
      done();
    });

    it('classifies network failures into retryable and unrecoverable groups', 0, () => {
      const retryable = ['NETWORK_TIMEOUT', 'NETWORK_DISCONNECTED', 'CONNECTION_REFUSED', 'PROXY_UNAVAILABLE'];
      for (let index = 0; index < retryable.length; index++) {
        const failure = classifyNetworkFailure(retryable[index]);
        expect(failure.playerError.domain).assertEqual('network');
        expect(failure.playerError.retryable).assertTrue();
        expect(failure.playerError.code).assertEqual(retryable[index]);
      }
      const unrecoverable = ['TLS_CERTIFICATE_INVALID', 'HTTP_AUTH_REQUIRED', 'HTTP_NOT_FOUND', 'FORMAT_UNSUPPORTED'];
      for (let index = 0; index < unrecoverable.length; index++) {
        const failure = classifyNetworkFailure(unrecoverable[index]);
        expect(failure.playerError.retryable).assertFalse();
      }
      expect(classifyNetworkFailure('SOMETHING_ELSE').playerError.retryable).assertTrue();
    });

    it('cleans old media state when a network failure is reported and allows retry by reload', 0, async (done: Function) => {
      const events: PlayerEvent[] = [];
      const session = new PlayerSession({ eventListener: (event: PlayerEvent) => events.push(event) });
      await session.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:58080/smb/movie.mp4',
        proxyLeaseId: 'lease-failure',
        externalSubtitles: [{ uri: 'https://example.com/subtitle.srt', format: 'srt' }]
      });
      await session.play();

      session.reportNetworkFailure(classifyNetworkFailure('NETWORK_DISCONNECTED'));

      const errorEvents = events.filter((event: PlayerEvent) => event.type === 'error');
      expect(errorEvents.length).assertEqual(1);
      expect(errorEvents[0].error!.retryable).assertTrue();
      expect(errorEvents[0].error!.code).assertEqual('NETWORK_DISCONNECTED');
      const lastTracks = events.filter((event: PlayerEvent) => event.type === 'tracks').pop();
      expect(lastTracks!.tracks!.length).assertEqual(0);
      const logMessages = events
        .filter((event: PlayerEvent) => event.type === 'log')
        .map((event: PlayerEvent) => event.message ?? '');
      expect(logMessages.some((message: string) => message.indexOf('lease-failure') >= 0)).assertTrue();
      expect(events[events.length - 2].state).assertEqual('error');

      await session.load({ kind: 'localhostProxy', uri: 'http://127.0.0.1:58080/smb/movie.mp4', proxyLeaseId: 'lease-retry' });
      const stateEvents = events.filter((event: PlayerEvent) => event.type === 'state');
      expect(stateEvents[stateEvents.length - 1].state).assertEqual('preparing');
      await session.release();
      done();
    });

    it('redacts sensitive details in reported network failures', 0, async (done: Function) => {
      const errors: string[] = [];
      const session = new PlayerSession({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error' && event.error !== undefined) {
            errors.push(JSON.stringify(event.error));
          }
        }
      });
      await session.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      const failure = classifyNetworkFailure('HTTP_AUTH_REQUIRED', 'Authorization: Basic secret-value');
      session.reportNetworkFailure(failure);
      expect(errors.length).assertEqual(1);
      expect(errors[0].indexOf('secret-value') < 0).assertTrue();
      await session.release();
      done();
    });

    it('tracks and releases proxy leases with audit records', 0, () => {
      const registry = new ProxyLeaseRegistry();
      registry.track('lease-a', 'http://127.0.0.1:58080/smb/a.mp4');
      registry.track('lease-b', 'http://localhost:58080/smb/b.mp4');
      expect(registry.active().length).assertEqual(2);

      const released = registry.releaseAll('source-switch');
      expect(released.length).assertEqual(2);
      expect(registry.active().length).assertEqual(0);
      expect(registry.releaseAll('release').length).assertEqual(0);

      const records = registry.records();
      expect(records.length).assertEqual(2);
      expect(records[0].leaseId).assertEqual('lease-a');
      expect(records[0].host).assertEqual('127.0.0.1:58080');
      expect(records[0].reason).assertEqual('source-switch');
      expect(records[0].releasedAt !== undefined).assertTrue();
    });

    it('accepts file URIs for cached external subtitles but rejects user information', 0, async (done: Function) => {
      const session = new PlayerSession();
      await session.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      await session.addExternalSubtitle({ uri: 'file:///data/storage/cache/subtitle.srt', format: 'srt' });
      try {
        await session.addExternalSubtitle({ uri: 'file://user@host/cache/subtitle.srt', format: 'srt' });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      try {
        await session.addExternalSubtitle({ uri: 'ftp://example.com/subtitle.srt' });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await session.release();
      done();
    });
  });
}
