import { describe, expect, it } from '@ohos/hypium';
import {
  buildBasicAuthorization,
  buildRawPropfindRequest,
  buildWebDavPlaybackHeaders,
  createPropfindRequestOptions,
  isSafeRedirect,
  parseRawHttpPropfindResponse,
  joinWebDavUrl,
  parseWebDavDirectory,
  sanitizeWebDavConfig,
  WebDavConfig
} from '../../../../main/ets/webdav/WebDavService';
import {
  canForwardAuthorization,
  authorizationHeadersForRedirect,
  validateMediaSource
} from '@vidall/player/src/internal/inputValidator';
import {
  buildSmbMediaUri,
  sanitizeSmbConfig,
  SmbConfig
} from '../../../../main/ets/smb/SmbService';

export default function webDavServiceTest() {
  describe('WebDavServiceTest', () => {
    it('builds an authorization header without exposing the password in configuration', 0, () => {
      const config: WebDavConfig = {
        endpoint: 'https://dav.example.com/library/',
        username: 'alice',
        password: 'correct-horse-battery-staple'
      };
      const saved = sanitizeWebDavConfig(config);

      expect(buildBasicAuthorization(config.username, config.password)).assertEqual('Basic YWxpY2U6Y29ycmVjdC1ob3JzZS1iYXR0ZXJ5LXN0YXBsZQ==');
      expect(saved.password).assertEqual('');
      expect(saved.endpoint).assertEqual('https://dav.example.com/library/');
      expect(saved.username).assertEqual('alice');
    });

    it('builds credential-free SMB media URIs and never persists its password', 0, () => {
      const config: SmbConfig = {
        host: '192.168.3.59',
        share: 'Media Library',
        path: 'Movies/电影 01.mkv',
        username: 'alice',
        password: 'correct-horse-battery-staple'
      };
      const saved = sanitizeSmbConfig(config);
      const uri = buildSmbMediaUri(config);

      expect(uri).assertEqual('smb://192.168.3.59/Media%20Library/Movies/%E7%94%B5%E5%BD%B1%2001.mkv');
      expect(uri.indexOf('alice') < 0).assertTrue();
      expect(uri.indexOf('correct-horse-battery-staple') < 0).assertTrue();
      expect(saved.password).assertEqual('');
      expect(saved.host).assertEqual('192.168.3.59');
      expect(saved.share).assertEqual('Media Library');
      expect(saved.path).assertEqual('Movies/电影 01.mkv');
      expect(saved.username).assertEqual('alice');
    });

    it('rejects invalid SMB host, share, and traversal path input', 0, () => {
      let hostRejected = false;
      try {
        buildSmbMediaUri({ host: 'alice@files.example', share: 'media', path: '', username: '', password: '' });
      } catch (_) {
        hostRejected = true;
      }
      let shareRejected = false;
      try {
        buildSmbMediaUri({ host: 'files.example', share: '', path: '', username: '', password: '' });
      } catch (_) {
        shareRejected = true;
      }
      let pathRejected = false;
      try {
        buildSmbMediaUri({ host: 'files.example', share: 'media', path: '../secret.mkv', username: '', password: '' });
      } catch (_) {
        pathRejected = true;
      }

      expect(hostRejected).assertTrue();
      expect(shareRejected).assertTrue();
      expect(pathRejected).assertTrue();
    });

    it('builds a real PROPFIND request for API 19 HTTP servers', 0, () => {
      const request = buildRawPropfindRequest('192.168.3.59:5005', 'Basic token');

      expect(request.startsWith('PROPFIND / HTTP/1.1\r\n')).assertTrue();
      expect(request).assertContain('Host: 192.168.3.59:5005\r\n');
      expect(request).assertContain('Authorization: Basic token\r\n');
      expect(request).assertContain('Content-Length: 116\r\n');
      expect(request).assertContain('<propfind');
    });

    it('rejects control characters in raw HTTP request fields', 0, () => {
      let hostRejected = false;
      try {
        buildRawPropfindRequest('dav.example.com\r\nX-Injected: true', 'Basic token');
      } catch (_) {
        hostRejected = true;
      }
      let authorizationRejected = false;
      try {
        buildRawPropfindRequest('dav.example.com', 'Basic token\nX-Injected: true');
      } catch (_) {
        authorizationRejected = true;
      }
      expect(hostRejected).assertTrue();
      expect(authorizationRejected).assertTrue();
    });

    it('decodes a chunked raw HTTP response before XML parsing', 0, () => {
      const response = 'HTTP/1.1 207 Multi-Status\r\nTransfer-Encoding: chunked\r\n\r\n' +
        '6\r\n<root>\r\n7\r\nvalue</\r\n5\r\nroot>\r\n0\r\n\r\n';
      expect(parseRawHttpPropfindResponse(response)).assertEqual('<root>value</root>');
    });

    it('uses byte lengths when decoding UTF-8 chunked responses', 0, () => {
      const response = 'HTTP/1.1 207 Multi-Status\r\nTransfer-Encoding: chunked\r\n\r\n' +
        '6\r\n电影\r\n0\r\n\r\n';
      expect(parseRawHttpPropfindResponse(response)).assertEqual('电影');
    });

    // 回归测试：分块边界切断 UTF-8 多字节字符时不抛异常，
    // 而是截断到最后一个完整字符边界。
    it('handles chunk boundaries that split multi-byte UTF-8 sequences gracefully', 0, () => {
      // "电影" 的 UTF-8 编码为 6 字节（每字 3 字节：E7 94 B5 E5 BD B1）。
      // 模拟第一个分块只包含 4 字节（"电"完整 + "影"的前 1 字节被截断），
      // 第二个分块包含剩余字节。由于 ArkTS 字符串已解码，无法精确模拟字节切分，
      // 所以我们测试一个不完整字节长度的分块——解码器应以 trailer \r\n 为锚点，
      // 截断到安全边界而非抛异常。
      const response = 'HTTP/1.1 207 Multi-Status\r\nTransfer-Encoding: chunked\r\n\r\n' +
        '4\r\n电\r\n0\r\n\r\n';
      // "电" 在 UTF-8 中占 3 字节，声明 4 字节的分块意味着多出 1 字节无法形成完整字符，
      // 解码器应截断到 "电"（3 字节）而非抛出异常。
      const result = parseRawHttpPropfindResponse(response);
      expect(result).assertEqual('电');
    });

    it('keeps NetworkKit options for newer API levels', 0, () => {
      const options = createPropfindRequestOptions('alice', 'secret');

      expect(options.method).assertEqual('POST');
      expect(options.customMethod).assertEqual('PROPFIND');
      expect(options.extraData).assertContain('<propfind');
    });

    it('resolves directory navigation without losing endpoint path or encoding names', 0, () => {
      expect(joinWebDavUrl('https://dav.example.com/media', '电影 01/')).assertEqual(
        'https://dav.example.com/media/%E7%94%B5%E5%BD%B1%2001/');
      expect(joinWebDavUrl('https://dav.example.com/media/folder/', '../clip.mp4')).assertEqual(
        'https://dav.example.com/media/clip.mp4');
    });

    it('parses folders and media files while excluding the requested collection itself', 0, () => {
      const xml = `<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:">
          <d:response><d:href>/media/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
          <d:response><d:href>/media/Movies/</d:href><d:propstat><d:prop><d:displayname>Movies</d:displayname><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
          <d:response><d:href>/media/trailer.mp4</d:href><d:propstat><d:prop><d:displayname>trailer.mp4</d:displayname><d:getcontentlength>1024</d:getcontentlength><d:resourcetype/></d:prop></d:propstat></d:response>
          <d:response><d:href>/media/notes.txt</d:href><d:propstat><d:prop><d:displayname>notes.txt</d:displayname><d:resourcetype/></d:prop></d:propstat></d:response>
        </d:multistatus>`;
      const entries = parseWebDavDirectory(xml, 'https://dav.example.com/media/');

      expect(entries.length).assertEqual(2);
      expect(entries[0].name).assertEqual('Movies');
      expect(entries[0].isDirectory).assertTrue();
      expect(entries[1].name).assertEqual('trailer.mp4');
      expect(entries[1].size).assertEqual(1024);
    });

    it('rejects invalid endpoint and unsupported file types', 0, () => {
      expect(joinWebDavUrl('not-a-url', 'clip.mp4')).assertEqual('');
      const xml = `<d:multistatus xmlns:d="DAV:"><d:response><d:href>/media/image.jpg</d:href><d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat></d:response></d:multistatus>`;
      expect(parseWebDavDirectory(xml, 'https://dav.example.com/media/').length).assertEqual(0);
    });

    // T034: WebDAV 安全存储引用配置

    it('rejects non-HTTP(S) endpoints in sanitized config', 0, () => {
      let ftpRejected = false;
      try {
        sanitizeWebDavConfig({ endpoint: 'ftp://dav.example.com/', username: 'alice', password: 'secret' });
      } catch (_) {
        ftpRejected = true;
      }
      let emptyRejected = false;
      try {
        sanitizeWebDavConfig({ endpoint: '', username: '', password: '' });
      } catch (_) {
        emptyRejected = true;
      }
      expect(ftpRejected).assertTrue();
      expect(emptyRejected).assertTrue();
    });

    it('accepts valid HTTP and HTTPS endpoints in sanitized config', 0, () => {
      const httpConfig = sanitizeWebDavConfig({ endpoint: 'http://192.168.1.10:5005/', username: 'alice', password: 'secret' });
      expect(httpConfig.endpoint).assertEqual('http://192.168.1.10:5005/');
      expect(httpConfig.password).assertEqual('');

      const httpsConfig = sanitizeWebDavConfig({ endpoint: 'https://dav.example.com/library/', username: 'bob', password: 'secret' });
      expect(httpsConfig.endpoint).assertEqual('https://dav.example.com/library/');
      expect(httpsConfig.password).assertEqual('');
    });

    it('never persists password in sanitized config even when username is present', 0, () => {
      const config: WebDavConfig = {
        endpoint: 'https://dav.example.com/',
        username: 'alice',
        password: 'super-secret-password-123'
      };
      const saved = sanitizeWebDavConfig(config);
      expect(saved.password).assertEqual('');
      expect(saved.username).assertEqual('alice');
      expect(saved.endpoint).assertEqual('https://dav.example.com/');
    });

    // T036: 认证、重定向、Range 与脱敏策略

    it('forwards Authorization only to the same scheme, host and port', 0, () => {
      // 同源同端口：允许转发
      expect(canForwardAuthorization(
        'https://dav.example.com/media/',
        'https://dav.example.com/media/file.mp4'
      )).assertTrue();

      // 同源不同端口：禁止转发
      expect(canForwardAuthorization(
        'https://dav.example.com:443/media/',
        'https://dav.example.com:8443/media/file.mp4'
      )).assertFalse();

      // 不同主机：禁止转发
      expect(canForwardAuthorization(
        'https://dav.example.com/media/',
        'https://other.example.com/media/file.mp4'
      )).assertFalse();

      // 协议降级 HTTPS→HTTP：禁止转发
      expect(canForwardAuthorization(
        'https://dav.example.com/media/',
        'http://dav.example.com/media/file.mp4'
      )).assertFalse();
    });

    it('strips Authorization and Cookie on cross-origin or protocol-downgrade redirects', 0, () => {
      const headers: Record<string, string> = {
        'authorization': 'Basic c2VjcmV0',
        'cookie': 'session=abc123',
        'accept': 'application/xml',
        'user-agent': 'VidAll/1.0'
      };

      // 跨源重定向：剥离 authorization 和 cookie
      const filtered = authorizationHeadersForRedirect(headers, 'https://dav.example.com/', 'https://other.example.com/');
      expect(filtered['authorization']).assertEqual(undefined);
      expect(filtered['cookie']).assertEqual(undefined);
      expect(filtered['accept']).assertEqual('application/xml');
      expect(filtered['user-agent']).assertEqual('VidAll/1.0');

      // 同源重定向：保留全部
      const kept = authorizationHeadersForRedirect(headers, 'https://dav.example.com/', 'https://dav.example.com/file.mp4');
      expect(kept['authorization']).assertEqual('Basic c2VjcmV0');
      expect(kept['cookie']).assertEqual('session=abc123');
    });

    it('identifies safe redirects that preserve scheme, host and port', 0, () => {
      // 同源同端口：安全重定向
      expect(isSafeRedirect('https://dav.example.com/media/', 'https://dav.example.com/media/file.mp4')).assertTrue();

      // 不同端口：不安全
      expect(isSafeRedirect('https://dav.example.com/', 'https://dav.example.com:8443/')).assertFalse();

      // 不同主机：不安全
      expect(isSafeRedirect('https://dav.example.com/', 'https://cdn.example.com/')).assertFalse();

      // 协议降级：不安全
      expect(isSafeRedirect('https://dav.example.com/', 'http://dav.example.com/')).assertFalse();
    });

    it('builds playback headers with Authorization and Range without leaking credentials', 0, () => {
      const headers = buildWebDavPlaybackHeaders('alice', 'secret', 0, 1048575);
      expect(headers['Authorization']).assertEqual('Basic YWxpY2U6c2VjcmV0');
      expect(headers['Range']).assertEqual('bytes=0-1048575');

      // 无 Range 请求
      const noRange = buildWebDavPlaybackHeaders('alice', 'secret');
      expect(noRange['Range']).assertEqual(undefined);
      expect(noRange['Authorization']).assertEqual('Basic YWxpY2U6c2VjcmV0');
    });

    it('builds playback headers without Authorization when credentials are empty', 0, () => {
      const headers = buildWebDavPlaybackHeaders('', '');
      expect(headers['Authorization']).assertEqual(undefined);
      expect(headers['Range']).assertEqual(undefined);
    });

    it('accepts WebDAV http and https sources with Authorization headers', 0, async (done: Function) => {
      // WebDAV 播放使用 http/https kind，Authorization 通过 headers 传递
      try {
        validateMediaSource({
          kind: 'https',
          uri: 'https://dav.example.com/media/video.mp4',
          headers: { 'authorization': 'Basic dGVzdDp0ZXN0' }
        });
        expect(true).assertTrue();
      } catch (_) {
        expect(true).assertFalse();
      }

      try {
        validateMediaSource({
          kind: 'http',
          uri: 'http://192.168.1.10:5005/media/video.mp4',
          headers: { 'authorization': 'Basic dGVzdDp0ZXN0' }
        });
        expect(true).assertTrue();
      } catch (_) {
        expect(true).assertFalse();
      }
      done();
    });

    it('rejects WebDAV URIs with userinfo before reaching authentication', 0, async (done: Function) => {
      let rejected = false;
      try {
        validateMediaSource({
          kind: 'https',
          uri: 'https://alice:secret@dav.example.com/media/video.mp4'
        });
      } catch (error) {
        rejected = true;
      }
      expect(rejected).assertTrue();
      done();
    });
  });
}
