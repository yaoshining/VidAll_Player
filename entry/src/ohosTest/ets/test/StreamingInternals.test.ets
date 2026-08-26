import { describe, expect, it } from '@ohos/hypium';
import { PlayerEvent } from '@vidall/player';
import { PlayerSession } from '@vidall/player/src/main/ets/internal/playerSession';
import { ProxyLeaseRegistry } from '@vidall/player/src/main/ets/internal/proxyLeaseRegistry';
import { classifyNetworkFailure } from '@vidall/player/src/main/ets/internal/networkRecovery';
import { canForwardAuthorization, authorizationHeadersForRedirect, validateMediaSource } from '@vidall/player/src/main/ets/internal/inputValidator';
import { redactText, redactContext, redactError } from '@vidall/player/src/main/ets/internal/redaction';
import { runHarNativePackagingProbe } from '@vidall/player/src/main/ets/native/harNativePackagingProbe';

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
      const leaseEvents = events.filter((event: PlayerEvent) => event.type === 'proxyLease');
      expect(leaseEvents.some((event: PlayerEvent) =>
        event.lease!.leaseId === 'lease-failure' && event.lease!.state === 'releaseRequested'
      )).assertTrue();
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

    it('rejects external subtitle edits after a reported network failure', 0, async (done: Function) => {
      let errored = false;
      const session = new PlayerSession({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error') {
            errored = true;
          }
        }
      });
      await session.load({ kind: 'https', uri: 'https://example.com/video.mp4' });
      const failure = classifyNetworkFailure('HTTP_AUTH_REQUIRED', 'Authorization: Basic secret');
      session.reportNetworkFailure(failure);
      expect(errored).assertTrue();

      try {
        await session.addExternalSubtitle({ uri: 'https://example.com/subtitle.srt', format: 'srt' });
        expect(true).assertFalse();
      } catch (_) {
        expect(true).assertTrue();
      }
      await session.release();
      done();
    });

    it('tracks lease epochs and waits for the current release confirmation', 0, () => {
      const registry = new ProxyLeaseRegistry();
      const acquired = registry.track('lease-a', 'http://127.0.0.1:58080/smb/a.mp4', 7);
      expect(acquired!.state).assertEqual('acquired');
      expect(acquired!.epoch).assertEqual(7);
      expect(registry.active().length).assertEqual(1);

      const requested = registry.requestReleaseAll('source-switch');
      expect(requested.length).assertEqual(1);
      expect(requested[0].state).assertEqual('releaseRequested');
      expect(registry.active().length).assertEqual(1);
      expect(registry.requestReleaseAll('release').length).assertEqual(0);
      expect(registry.confirmReleased('lease-a', 6) === undefined).assertTrue();
      expect(registry.confirmReleased('lease-a', 7)!.state).assertEqual('released');
      expect(registry.active().length).assertEqual(0);

      const records = registry.records();
      expect(records[0].host).assertEqual('127.0.0.1:58080');
      expect(records[0].reason).assertEqual('source-switch');
    });

    it('ignores stale lease acquisition epochs', 0, () => {
      const registry = new ProxyLeaseRegistry();
      const current = registry.track('lease-stale', 'http://127.0.0.1:58080/smb/a.mp4', 7);
      const stale = registry.track('lease-stale', 'http://127.0.0.1:58080/smb/a.mp4', 6);
      expect(current!.epoch).assertEqual(7);
      expect(stale!.epoch).assertEqual(7);
      expect(stale!.state).assertEqual('acquired');
    });

    it('emits acquired and releaseRequested lease states without claiming cleanup completed', 0, async (done: Function) => {
      const leases: PlayerEvent[] = [];
      const session = new PlayerSession({ eventListener: (event: PlayerEvent) => {
        if (event.type === 'proxyLease') {
          leases.push(event);
        }
      }});
      await session.load({ kind: 'localhostProxy', uri: 'http://localhost:58080/smb/movie.mp4', proxyLeaseId: 'lease-events' });
      await session.stop();
      expect(leases.length).assertEqual(2);
      expect(leases[0].lease!.state).assertEqual('acquired');
      expect(leases[1].lease!.state).assertEqual('releaseRequested');
      expect(leases[0].lease!.epoch).assertEqual(1);
      expect(leases[1].lease!.epoch).assertEqual(1);
      await session.release();
      done();
    });

    it('loads the HAR-internal native probe and confirms the session round-trip', 0, () => {
      const result = runHarNativePackagingProbe();
      console.info(`HAR_NATIVE_PROBE created=${result.created}; code=${result.code}`);
      expect(result.created).assertTrue();
      expect(result.code).assertEqual('OK');
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

    // T036: 重定向安全策略测试

    it('strips Authorization headers when redirect crosses to a different port', 0, () => {
      const headers: Record<string, string> = {
        'authorization': 'Basic c2VjcmV0',
        'accept': '*/*'
      };
      const filtered = authorizationHeadersForRedirect(
        headers,
        'https://dav.example.com:443/media/',
        'https://dav.example.com:8443/redirect/'
      );
      expect(filtered!['authorization']).assertEqual(undefined);
      expect(filtered!['accept']).assertEqual('*/*');
    });

    it('preserves Authorization when redirect stays on same scheme, host and port', 0, () => {
      const headers: Record<string, string> = {
        'authorization': 'Basic c2VjcmV0',
        'accept': '*/*'
      };
      const kept = authorizationHeadersForRedirect(
        headers,
        'https://dav.example.com/media/',
        'https://dav.example.com/media/video.mp4'
      );
      expect(kept!['authorization']).assertEqual('Basic c2VjcmV0');
      expect(kept!['accept']).assertEqual('*/*');
    });

    it('handles IPv6 authority equivalence with and without explicit default port', 0, () => {
      // IPv6 无显式端口 vs 有显式默认端口：应视为同源
      expect(canForwardAuthorization(
        'https://[::1]/media/',
        'https://[::1]:443/media/file.mp4'
      )).assertTrue();

      expect(canForwardAuthorization(
        'http://[::1]/media/',
        'http://[::1]:80/media/file.mp4'
      )).assertTrue();

      // IPv6 同源同端口：允许转发
      expect(canForwardAuthorization(
        'https://[::1]:443/media/',
        'https://[::1]:443/media/file.mp4'
      )).assertTrue();

      // IPv6 不同端口：禁止转发
      expect(canForwardAuthorization(
        'https://[::1]/media/',
        'https://[::1]:8443/media/file.mp4'
      )).assertFalse();
    });

    // T038: 受控 WebDAV 集成测试

    it('redacts Authorization and token values from error context', 0, () => {
      const context = redactContext({
        'authorization': 'Basic c2VjcmV0',
        'token': 'abc123',
        'url': 'https://dav.example.com/media/',
        'statusCode': 401
      });
      expect(context['authorization']).assertEqual('[REDACTED]');
      expect(context['token']).assertEqual('[REDACTED]');
      expect(context['url']).assertEqual('https://dav.example.com/media/');
      expect(context['statusCode']).assertEqual(401);
    });

    it('redacts credentials from network failure detail strings', 0, () => {
      const redacted = redactText('Authorization: Basic c2VjcmV0 failed for user alice');
      expect(redacted.indexOf('c2VjcmV0') < 0).assertTrue();
      expect(redacted.indexOf('Basic') >= 0).assertTrue();
    });

    it('classifies WebDAV auth failure as unrecoverable and TLS failure as unrecoverable', 0, () => {
      const authFailure = classifyNetworkFailure('HTTP_AUTH_REQUIRED', 'Wrong credentials');
      expect(authFailure.playerError.retryable).assertFalse();
      expect(authFailure.playerError.domain).assertEqual('network');

      const tlsFailure = classifyNetworkFailure('TLS_CERTIFICATE_INVALID', 'Self-signed cert');
      expect(tlsFailure.playerError.retryable).assertFalse();
    });

    it('classifies WebDAV timeout and disconnection as retryable', 0, () => {
      const timeoutFailure = classifyNetworkFailure('NETWORK_TIMEOUT');
      expect(timeoutFailure.playerError.retryable).assertTrue();

      const disconnectFailure = classifyNetworkFailure('NETWORK_DISCONNECTED');
      expect(disconnectFailure.playerError.retryable).assertTrue();
    });

    // T039: ArkTS 到 native headers 传递

    it('passes Authorization headers through MediaSource without exposing credentials in events', 0, async (done: Function) => {
      const events: PlayerEvent[] = [];
      const session = new PlayerSession({ eventListener: (event: PlayerEvent) => events.push(event) });
      await session.load({
        kind: 'https',
        uri: 'https://dav.example.com/media/video.mp4',
        headers: { 'authorization': 'Basic c2VjcmV0' }
      });

      // 验证：源已加载且 headers 已存储
      // 日志和事件中不应出现凭据
      const logMessages = events
        .filter((e: PlayerEvent) => e.type === 'log' && e.log !== undefined)
        .map((e: PlayerEvent) => e.log!.message);
      for (let index = 0; index < logMessages.length; index++) {
        expect(logMessages[index].indexOf('c2VjcmV0') < 0).assertTrue();
      }
      await session.release();
      done();
    });

    it('redacts Authorization in error events for WebDAV playback failures', 0, async (done: Function) => {
      const errors: PlayerEvent[] = [];
      const session = new PlayerSession({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'error') {
            errors.push(event);
          }
        }
      });
      await session.load({
        kind: 'https',
        uri: 'https://dav.example.com/media/video.mp4',
        headers: { 'authorization': 'Basic c2VjcmV0' }
      });

      // 模拟网络上报认证失败
      const failure = classifyNetworkFailure('HTTP_AUTH_REQUIRED', 'Authorization: Basic c2VjcmV0 rejected');
      session.reportNetworkFailure(failure);

      expect(errors.length).assertEqual(1);
      // 脱敏后的错误不应包含凭据
      const errorJson = JSON.stringify(errors[0].error);
      expect(errorJson.indexOf('c2VjcmV0') < 0).assertTrue();
      await session.release();
      done();
    });

    it('validates WebDAV HTTPS source with headers and rejects URI with userinfo', 0, () => {
      // 有效 HTTPS WebDAV 源
      validateMediaSource({
        kind: 'https',
        uri: 'https://dav.example.com/media/video.mp4',
        headers: { 'authorization': 'Basic dGVzdDp0ZXN0', 'range': 'bytes=0-' }
      });

      // 拒绝含 userinfo 的 URI
      let rejected = false;
      try {
        validateMediaSource({
          kind: 'https',
          uri: 'https://user:pass@dav.example.com/media/video.mp4'
        });
      } catch (_) {
        rejected = true;
      }
      expect(rejected).assertTrue();
    });

    // T040: 敏感信息扫描

    it('never includes raw credentials in proxy lease release log messages', 0, async (done: Function) => {
      const logMessages: string[] = [];
      const session = new PlayerSession({
        eventListener: (event: PlayerEvent) => {
          if (event.type === 'log' && event.message !== undefined) {
            logMessages.push(event.message);
          }
        }
      });
      await session.load({
        kind: 'localhostProxy',
        uri: 'http://127.0.0.1:58080/dav/video.mp4?token=secret-abc',
        proxyLeaseId: 'lease-credential-scan',
        headers: { 'authorization': 'Basic c2VjcmV0' }
      });
      await session.stop();
      for (let index = 0; index < logMessages.length; index++) {
        expect(logMessages[index].indexOf('secret-abc') < 0).assertTrue();
        expect(logMessages[index].indexOf('c2VjcmV0') < 0).assertTrue();
      }
      await session.release();
      done();
    });

    it('redacts sensitive query parameters and file paths in error messages', 0, () => {
      const redacted = redactText(
        'Failed to load https://dav.example.com/media/?access_token=secret123&api_key=key456'
      );
      expect(redacted.indexOf('secret123') < 0).assertTrue();
      expect(redacted.indexOf('key456') < 0).assertTrue();
      expect(redacted.indexOf('[REDACTED_QUERY]') >= 0).assertTrue();
    });
  });
}
