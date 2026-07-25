#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo '用法：generate-libmpv-manifest.sh --lock <sources.lock.json> --source <目录> --output <文件> --abi <ABI> --min-sdk <API> [--build-time <epoch>]' >&2
  exit 2
}

lock_file=''
source_dir=''
output_file=''
abi=''
min_sdk=''
build_time="${SOURCE_DATE_EPOCH:-$(date +%s)}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --lock) lock_file="$2"; shift 2 ;;
    --source) source_dir="$2"; shift 2 ;;
    --output) output_file="$2"; shift 2 ;;
    --abi) abi="$2"; shift 2 ;;
    --min-sdk) min_sdk="$2"; shift 2 ;;
    --build-time) build_time="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[ -f "$lock_file" ] && [ -d "$source_dir" ] && [ -n "$output_file" ] && [ -n "$abi" ] && [ -n "$min_sdk" ] || usage
mkdir -p "$(dirname "$output_file")"

python3 - "$lock_file" "$source_dir" "$output_file" "$abi" "$min_sdk" "$build_time" <<'PY'
import datetime
import json
import pathlib
import sys

lock_path, source_path, output_path, abi, min_sdk, epoch = sys.argv[1:]
source = pathlib.Path(source_path)
lock = json.loads(pathlib.Path(lock_path).read_text(encoding='utf-8'))

def lines(path):
    file = source / path
    if not file.is_file():
        return []
    return [line.strip() for line in file.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]

build_time = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest = {
    'schemaVersion': 1,
    'abi': abi,
    'minSdk': int(min_sdk),
    'buildTime': build_time,
    'sourceCommits': {name: value['commit'] for name, value in lock['sources'].items()},
    'ffmpeg': {
        'configureOptions': lines('ffmpeg/configure-options.txt'),
        'components': {
            'demuxers': lines('ffmpeg/demuxers.txt'),
            'protocols': lines('ffmpeg/protocols.txt'),
            'decoders': lines('ffmpeg/decoders.txt'),
            'encoders': lines('ffmpeg/encoders.txt'),
            'filters': lines('ffmpeg/filters.txt'),
        },
    },
    'mpv': {'mesonOptions': lines('mpv/meson-options.txt')},
    'dynamicDependencies': lines('dynamic-dependencies.txt'),
}
pathlib.Path(output_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
