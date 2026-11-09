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
    """提取原始函数定义，在宿主测试中直接编译。"""
    match = re.search(r'^(?:static )?[\w *]+\b' + name + r'\([^;]*?\)\s*\n\{.*?^\}', source, re.M | re.S)
    if not match:
        raise AssertionError(f'缺少生产函数 {name}')
    return match[0]

def source(rel):
    """从传入的 mpv 源树读取文件。"""
    return (args.mpv / rel).read_text()

driver = source('audio/out/ao_ohaudio.c')
core = source('player/audio.c')
ao = source('audio/out/ao.c')
assert 'OH_AudioStreamBuilder_SetRendererCallback(' in driver, '旧系统只注册写入回调，无法接收闹铃中断'
assert 'res = register_callbacks(ao);' in function(driver, 'init')
assert re.search(r'res = register_callbacks\(ao\);\s*if \(res != AUDIOSTREAM_SUCCESS\).*?goto error;', driver, re.S)
assert 'handle_audio_interrupt(mpctx);' in function(core, 'fill_audio_out_buffers')
def conditional(file, start, end):
    """保留指定边界之间的生产分支代码。"""
    body = source(file).split(start, 1)[1].split(end, 1)[0]
    return body.strip()

unload = conditional('player/loadfile.c', '    uninit_sub_all(mpctx);\n    if (', '    mpctx->playback_initialized')
assert 'uninit_audio_out(mpctx);' in unload
apply_pause = conditional('player/command.c', '    if (opt_ptr == &opts->pause)', '    if (opt_ptr == &opts->audio_delay)')
binding = driver[driver.index('struct legacy_binding {'):driver.index('struct priv {')]
registry = driver[driver.index('static pthread_rwlock_t legacy_lock'):driver.index('static void reset_timing')]

parts = [
    function(ao, 'ao_add_events'), function(ao, 'ao_query_and_reset_events'),
    function(ao, 'ao_request_pause'), function(ao, 'ao_is_per_file'), registry,
    function(driver, 'uninit'), function(driver, 'legacy_write'),
    function(driver, 'legacy_interrupt'), function(driver, 'register_callbacks'),
    function(source('player/playloop.c'), 'get_internal_paused'),
    function(source('player/playloop.c'), 'update_internal_pause_state'),
    function(source('player/playloop.c'), 'step_frame_mute'),
    function(source('player/playloop.c'), 'set_pause_state'),
    function(core, 'handle_audio_interrupt'), function(source('player/playloop.c'), 'add_step_frame'),
    'static void unload(struct MPContext *mpctx) { struct MPOpts *opts = mpctx->opts; if (' + unload + '}',
    'static void set_user_pause_option(struct MPContext *mpctx, bool pause) { struct MPOpts *opts = mpctx->opts; opts->pause = pause; ' + apply_pause + '}',

]
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    program = (here / 'harness.c').read_text().replace('/* PRODUCTION */', '\n'.join(parts))
    (td / 'test.c').write_text(program.replace('/* BINDING */', binding))
    subprocess.run(['cc', '-std=gnu11', '-pthread', '-Wall', '-Werror', str(td / 'test.c'), '-o', str(td / 'test')], check=True)
    subprocess.run([str(td / 'test')], check=True, timeout=10)
