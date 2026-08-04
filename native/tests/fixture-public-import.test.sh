#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly FIXTURE="$ROOT/fixtures/libmpv-player-consumer"
readonly PACKAGE="$FIXTURE/oh-package.json5"
readonly PAGE="$FIXTURE/src/main/ets/pages/Index.ets"
readonly MODULE="$FIXTURE/src/main/module.json5"
readonly TEST_MODULE="$FIXTURE/src/ohosTest/module.json5"
readonly TEST_FILE="$FIXTURE/src/ohosTest/ets/test/PublicImport.test.ets"

fail() { echo "测试失败：$*" >&2; exit 1; }
require_contains() { rg -q --fixed-strings "$2" "$1" || fail "$1 缺少：$2"; }

require_contains "$PACKAGE" '"@vidall/player": "file:../../packages/vidall-player/build/default/outputs/default/vidall_player.har"'
require_contains "$PAGE" "from '@vidall/player'"
require_contains "$PAGE" 'createPlayer()'
require_contains "$PAGE" 'player.release()'
require_contains "$PAGE" '模拟器仅用于开发期生命周期验证'
require_contains "$MODULE" '"deviceTypes": ["tv"]'
require_contains "$TEST_MODULE" '"name": "libmpv_player_consumer_test"'
require_contains "$TEST_FILE" "from '@vidall/player'"
require_contains "$TEST_FILE" 'createPlayer()'
require_contains "$TEST_FILE" 'await player.release()'
for forbidden in 'src/native' 'libvidall_player_native.so' 'libentry' 'NativeWindow' 'EGL' 'GLES' 'AVPlayer'; do
  ! rg -q --fixed-strings "$forbidden" "$PAGE" "$PACKAGE" "$MODULE" "$TEST_FILE" || fail "fixture 泄露或依赖受限符号：$forbidden"
done
