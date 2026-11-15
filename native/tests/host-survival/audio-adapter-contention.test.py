"""确定性模拟控制锁竞争：允许一次静音，永久静音仍必须失败。"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
adapter = ROOT / 'native/experimental/audio_output_adapter.c'
fixture = ROOT / 'native/tests/host-survival/audio-adapter.test.c'
source = adapter.read_text().replace('"audio_output_adapter.h"', '"' + str(adapter.with_suffix('.h')) + '"')
test = fixture.read_text().replace('"../../experimental/audio_output_adapter.h"', '"' + str(adapter.with_suffix('.h')) + '"')
needle = '    if (pthread_mutex_trylock(&o->lock))\n        return 0;'
assert source.count(needle) == 1
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    (p / 'fixture.c').write_text(test)
    for mode in ['once', 'forever']:
        inject = 'count++ == 0' if mode == 'once' else 'true'
        hook = '''    static int count;
    (void)count;
    bool inject = CONDITION;
    if (inject) pthread_mutex_lock(&o->lock);
    int busy = pthread_mutex_trylock(&o->lock);
    if (inject) pthread_mutex_unlock(&o->lock);
    if (busy) return 0;'''.replace('CONDITION', inject)
        (p / 'adapter.c').write_text(source.replace(needle, hook))
        subprocess.run(['clang', '-std=gnu11', '-pthread', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', str(p/'fixture.c'), str(p/'adapter.c'),
                        '-o', str(p/'test')], check=True)
        for case in (['normal', 'clock', 'pause-clock'] if mode == 'once' else ['normal']):
            result = subprocess.run([str(p/'test'), case], capture_output=True, text=True, timeout=5)
            if mode == 'once':
                assert result.returncode == 0, result.stderr
            else:
                assert result.returncode != 0 and 'read_pcm' in result.stderr, result.stderr
print('PASS 一次锁竞争后完整PCM与时钟；永久静音仍在有界期限失败')
