"""从锁定的 mpv 源码取生产函数，用 OHAudio 替身驱动同一注册路径。"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('mpv', type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
def function(source, name):
    match = re.search(r'^(?:static )?[\w *]+\b' + name + r'\([^;]*?\)\s*\n\{.*?^\}', source, re.M | re.S)
    if not match:
        raise AssertionError(f'缺少生产函数 {name}')
    return match[0]

def source(rel):
    return (args.mpv / rel).read_text()

driver = source('audio/out/ao_ohaudio.c')
core = source('player/audio.c')
ao = source('audio/out/ao.c')
assert 'OH_AudioStreamBuilder_SetRendererCallback(' in driver, '旧系统只注册写入回调，无法接收闹铃中断'
assert 'res = register_callbacks(ao);' in function(driver, 'init')
assert re.search(r'res = register_callbacks\(ao\);\s*if \(res != AUDIOSTREAM_SUCCESS\).*?goto error;', driver, re.S)
assert 'handle_audio_interrupt(mpctx);' in function(core, 'fill_audio_out_buffers')
assert 'ao_is_per_file(mpctx->ao)' in source('player/loadfile.c')
parts = [
    function(ao, 'ao_add_events'), function(ao, 'ao_query_and_reset_events'),
    function(ao, 'ao_request_pause'), function(driver, 'legacy_write'),
    function(driver, 'legacy_interrupt'), function(driver, 'register_callbacks'),
    function(core, 'handle_audio_interrupt'),
]
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    program = (here / 'harness.c').read_text().replace('/* PRODUCTION */', '\n'.join(parts))
    (td / 'test.c').write_text(program)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Werror', str(td / 'test.c'), '-o', str(td / 'test')], check=True)
    subprocess.run([str(td / 'test')], check=True)
