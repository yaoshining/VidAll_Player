import { describe, expect, it } from '@ohos/hypium';
import { detectMediaKind, isSmbDirectPlaybackSupported, newProxyLeaseId, SMB_UNSUPPORTED_MESSAGE } from '../../../../main/ets/player/MediaKindDetection';

export default function mediaKindDetectionTest() {
  describe('MediaKindDetectionTest', () => {
    it('detects HLS and DASH manifests by extension and query', 0, () => {
      expect(detectMediaKind('https://example.com/live/master.m3u8')).assertEqual('hls');
      expect(detectMediaKind('https://example.com/live/master.M3U8?token=abc')).assertEqual('hls');
      expect(detectMediaKind('http://example.com/vod/manifest.mpd')).assertEqual('dash');
      expect(detectMediaKind('https://example.com/vod/manifest.mpd?v=2')).assertEqual('dash');
    });

    it('detects localhost proxy sources for loopback hosts', 0, () => {
      expect(detectMediaKind('http://127.0.0.1:58080/smb/movie.mp4')).assertEqual('localhostProxy');
      expect(detectMediaKind('http://localhost:58080/smb/movie.mp4')).assertEqual('localhostProxy');
      expect(detectMediaKind('http://[::1]:58080/smb/movie.mp4')).assertEqual('localhostProxy');
    });

    it('detects credential-free direct SMB links', 0, () => {
      expect(detectMediaKind('smb://files.example/media/video.mkv')).assertEqual('smb');
    });

    it('falls back to https and http for direct links', 0, () => {
      expect(detectMediaKind('https://example.com/video.mp4')).assertEqual('https');
      expect(detectMediaKind('http://192.168.1.10/media/video.mkv')).assertEqual('http');
      expect(detectMediaKind('https://example.com/stream?format=hls')).assertEqual('https');
    });

    it('generates unique non-empty lease identifiers', 0, () => {
      const first = newProxyLeaseId();
      const second = newProxyLeaseId();
      expect(first.length > 0).assertTrue();
      expect(first !== second).assertTrue();
    });

    // 直连 SMB 依赖交叉编译 libsmbclient 到 libmpv.so，属于受控发布门禁（Issue #41），
    // 当前 nativeBridge.getDirectSmbCapability() 恒返回 false，因此演示层必须提前拦截，
    // 而不是让用户看到 SDK 内部的 HEADER_NOT_ALLOWED/PROTOCOL_NOT_AVAILABLE 校验码。
    it('reports direct smb playback as unsupported with a clear message', 0, () => {
      expect(isSmbDirectPlaybackSupported()).assertFalse();
      expect(SMB_UNSUPPORTED_MESSAGE.length > 0).assertTrue();
      expect(SMB_UNSUPPORTED_MESSAGE.indexOf('SMB') >= 0).assertTrue();
    });
  });
}
