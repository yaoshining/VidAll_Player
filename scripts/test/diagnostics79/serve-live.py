#!/usr/bin/env python3
"""只在 loopback 提供无长度、无结束的受控 MPEG-TS 流，用于直播缺失时长验收。"""
import argparse
import http.server
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('media', type=Path)
parser.add_argument('--port', type=int, default=18780)
args = parser.parse_args()
data = args.media.read_bytes()

class LiveHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/live.ts':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp2t')
        self.end_headers()
        try:
            while True:
                for start in range(0, len(data), 188 * 40):
                    self.wfile.write(data[start:start + 188 * 40])
                    self.wfile.flush()
                    time.sleep(0.04)
        except (BrokenPipeError, ConnectionResetError):
            pass

http.server.ThreadingHTTPServer(('127.0.0.1', args.port), LiveHandler).serve_forever()
