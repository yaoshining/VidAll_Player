#!/usr/bin/env python3
"""Credential-free loopback fixture for HTTP, WebDAV, redirects, Range, and chunked responses."""

import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

FIXTURE_AUTH = 'Basic Zml4dHVyZTpjcmVkZW50aWFs'
MEDIA = b'vidall-fixture-media'


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = 'VidAllFixture/1.0'

    def do_PROPFIND(self):
        if not self.path.startswith('/webdav'):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not self._authorized():
            self._challenge()
            return
        self.send_response(207)
        self.send_header('DAV', '1')
        self.send_header('Content-Type', 'application/xml; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<?xml version="1.0"?><multistatus xmlns="DAV:"/>')

    def do_OPTIONS(self):
        if not self.path.startswith('/webdav'):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not self._authorized():
            self._challenge()
            return

        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('DAV', '1')
        self.send_header('Allow', 'OPTIONS, GET, PROPFIND')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/redirect/same':
            self._redirect('/media/sample.mp4')
        elif path == '/redirect/cross':
            self._redirect('http://127.0.0.1:18081/media/sample.mp4')
        elif path == '/timeout':
            self.send_error(504, 'fixture timeout')
        elif path == '/chunked':
            self._chunked()
        elif path == '/webdav/media/sample.mp4':
            if self._authorized():
                self._media()
            else:
                self._challenge()
        elif path == '/media/sample.mp4':
            self._media()
        else:
            self.send_error(404)

    def _authorized(self):
        return self.headers.get('Authorization') == FIXTURE_AUTH

    def _challenge(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="vidall-fixture"')
        self.end_headers()

    def _redirect(self, target):
        self.send_response(302)
        self.send_header('Location', target)
        self.end_headers()

    def _chunked(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        for chunk in (b'fixture-', b'chunked-media'):
            self.wfile.write(f'{len(chunk):X}\r\n'.encode('ascii') + chunk + b'\r\n')
        self.wfile.write(b'0\r\n\r\n')

    def _media(self):
        payload = MEDIA
        requested_range = self.headers.get('Range')
        if requested_range == 'bytes=0-3':
            payload = payload[:4]
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header('Content-Range', 'bytes 0-3/{}'.format(len(MEDIA)))
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), FixtureHandler).serve_forever()
