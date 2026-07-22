import { describe, expect, it } from '@ohos/hypium';
import {
  buildBasicAuthorization,
  buildRawPropfindRequest,
  createPropfindRequestOptions,
  parseRawHttpPropfindResponse,
  joinWebDavUrl,
  parseWebDavDirectory,
  sanitizeWebDavConfig,
  WebDavConfig
} from '../../../../main/ets/webdav/WebDavService';

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
  });
}
