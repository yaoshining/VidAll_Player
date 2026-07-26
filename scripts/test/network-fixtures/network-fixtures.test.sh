#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
readonly FIXTURES="$ROOT/scripts/test/network-fixtures"
fail() { echo "夹具测试失败：$*" >&2; exit 1; }

[ -f "$FIXTURES/docker-compose.yml" ] || fail '缺少 compose 定义'
[ -f "$FIXTURES/fixture-server.py" ] || fail '缺少受控 HTTP/WebDAV/chunked 服务实现'
[ -f "$FIXTURES/Dockerfile" ] || fail '缺少夹具容器镜像定义'
grep -Fq '127.0.0.1:18080:8080' "$FIXTURES/docker-compose.yml" || fail '服务必须仅绑定 loopback'
grep -Fq 'PROPFIND' "$FIXTURES/fixture-server.py" || fail '服务必须实现 WebDAV PROPFIND'
grep -Fq 'do_OPTIONS' "$FIXTURES/fixture-server.py" || fail '服务必须声明 WebDAV OPTIONS'
grep -Fq 'Transfer-Encoding' "$FIXTURES/fixture-server.py" || fail '服务必须实现 chunked 响应'
grep -Fq 'Basic Zml4dHVyZTpjcmVkZW50aWFs' "$FIXTURES/fixture-server.py" || fail '服务必须校验 fixture Basic Authorization'
pycache_dir="$(mktemp -d)"
trap 'rm -rf "$pycache_dir"' EXIT
PYTHONPYCACHEPREFIX="$pycache_dir" python3 -m py_compile "$FIXTURES/fixture-server.py"

python3 - "$ROOT/release/audits/tdd-baseline.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    record = json.load(handle)
assert record['schemaVersion'] == 1
assert record['status'] == 'recorded'
assert record['t006']['outcome'] == 'blocked'
assert record['t006']['realBridgeAllowed'] is False
for phase, result in (('redPhase', 'failed-as-expected'), ('greenPhase', 'passed')):
    item = record['t008'][phase]
    assert item['result'] == result
    assert item['recordedAt']
    assert item['sourceCommit']
PY

port=18082
PORT="$port" python3 "$FIXTURES/fixture-server.py" &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  rm -rf "$pycache_dir"
}
trap cleanup EXIT

for _ in $(seq 1 20); do
  curl --silent --fail "http://127.0.0.1:$port/media/sample.mp4" >/dev/null && break
  sleep 0.1
done
curl --silent --fail --range 0-3 "http://127.0.0.1:$port/media/sample.mp4" | grep -Fxq 'vida' || fail 'Range 响应不正确'
curl --silent --fail "http://127.0.0.1:$port/chunked" | grep -Fxq 'fixture-chunked-media' || fail 'chunked 响应不正确'
[ "$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$port/redirect/same")" = '302' ] || fail '同源重定向响应不正确'
[ "$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$port/redirect/cross")" = '302' ] || fail '跨端口重定向响应不正确'
[ "$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$port/timeout")" = '504' ] || fail '超时响应不正确'
curl --silent --fail --user fixture:credential "http://127.0.0.1:$port/webdav/media/sample.mp4" >/dev/null || fail '认证 WebDAV 媒体响应不正确'
curl --silent --fail --user fixture:credential -X PROPFIND "http://127.0.0.1:$port/webdav/" | grep -Fq 'multistatus' || fail 'WebDAV PROPFIND 响应不正确'
curl --silent --fail --user fixture:credential -X OPTIONS -D - "http://127.0.0.1:$port/webdav/" | grep -Eqi '^DAV: 1' || fail 'WebDAV OPTIONS 响应不正确'
[ "$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$port/webdav/media/sample.mp4")" = '401' ] || fail '未认证 WebDAV 请求必须被拒绝'
[ "$(curl --silent --output /dev/null --write-out '%{http_code}' -X OPTIONS "http://127.0.0.1:$port/webdav/")" = '401' ] || fail '未认证 WebDAV OPTIONS 必须被拒绝'

printf '受控网络夹具和 TDD 基线记录校验通过\n'
