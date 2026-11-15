"""编译诊断的真实有界记录函数；不能用探针覆盖生产时钟。"""
from pathlib import Path
import subprocess,sys,tempfile
s=(Path(sys.argv[1])/'audio/out/ao_ohaudio.c').read_text()
a=s.index('// T066_TRACE_BEGIN');b=s.index('// T066_TRACE_END',a)
code='''#include <assert.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
'''+s[a:b]+'''
static struct probe_queue_trace t;
static void *writer(void*p){unsigned n=(uintptr_t)p;for(unsigned i=n;i<1024;i+=2)probe_record(&t,i,i,2,3,4,5,6,7,8,9);return 0;}
int main(void){
 assert(!atomic_load(&t.rows[0].ready));
 pthread_t a,b;pthread_create(&a,0,writer,(void*)0);pthread_create(&b,0,writer,(void*)1);
 pthread_join(a,0);pthread_join(b,0);
 for(unsigned i=0;i<64;i++){assert(atomic_load_explicit(&t.rows[i].ready,memory_order_acquire));assert(t.rows[i].enter==i);assert(t.rows[i].leave==2);assert(t.rows[i].samples==3);assert(t.rows[i].written==4);assert(t.rows[i].queued==5);assert(t.rows[i].pos==6);assert(t.rows[i].stamp==7);assert(t.rows[i].end==8);assert(t.rows[i].nonzero==9);}
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['clang','-std=c11','-Wall','-Werror','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS 64个记录槽/1024次并发回调/发布后读取/无越界')
