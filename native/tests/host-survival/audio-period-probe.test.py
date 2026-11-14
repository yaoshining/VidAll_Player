"""诊断回调粒度选择：成功/拒绝均记录，不能静默当作设置成功。"""
from pathlib import Path
import sys,subprocess,tempfile
s=(Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text();a=s.index('// T066_PERIOD_BEGIN');b=s.index('// T066_PERIOD_END',a)
code='''#include <assert.h>
static int result,calls,frames;
struct A{int samplerate;} value,*ao=&value;
struct P{int*builder;} state,*p=&state;
#define MP_WARN(...) ((void)0)
static int OH_AudioStreamBuilder_SetFrameSizeInCallback(int*b,int f){(void)b;calls++;frames=f;return result;}
static void probe(void){
'''+s[a:b]+'''
}
int main(){value.samplerate=48000;probe();assert(calls==1&&frames==960);result=-1;value.samplerate=44100;probe();assert(calls==2&&frames==882);}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'t.c').write_text(code);subprocess.run(['clang','-std=c11',str(p/'t.c'),'-o',str(p/'t')],check=True);subprocess.run([str(p/'t')],check=True)
print('PASS 20ms按采样率计算/拒绝不冒充成功')
