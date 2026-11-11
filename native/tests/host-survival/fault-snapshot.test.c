#include "host_recovery_api.h"
#include "ohcodec_terminal.h"
#include <mpv/ohcodec_terminal.h>
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
static bool known;
static void *fault(void *tagged) {
    if ((uintptr_t)tagged) mp_ohcodec_terminal_enter_context(-7,2,123,17,4);
    else mp_ohcodec_terminal_enter(-9,3,456);
    return NULL;
}
int main(int argc,char**argv) {
    assert(argc==2);known=!strcmp(argv[1],"known");
    mpv_host_fault_record out={.size=sizeof(out)};
    assert(mpv_host_fault_snapshot(&out)==0);
    out.size=0;assert(mpv_host_fault_snapshot(&out)<0);out.size=sizeof(out);
    pthread_t worker;assert(!pthread_create(&worker,NULL,fault,(void*)(uintptr_t)known));
    for(int i=0;i<1000&&mpv_host_fault_snapshot(&out)!=1;i++)usleep(1000);
    assert(out.session_id==(known?17:0)&&out.load_generation==(known?4:0));
    pthread_t late;assert(!pthread_create(&late,NULL,fault,(void*)(uintptr_t)!known));
    usleep(2000);assert(mpv_host_fault_snapshot(&out)==1);
    assert(out.session_id==(known?17:0)&&out.load_generation==(known?4:0));
    mpv_ohcodec_terminal_record legacy={.size=sizeof(legacy),.abi_version=MPV_OHCODEC_TERMINAL_ABI_VERSION};
    assert(mpv_ohcodec_terminal_snapshot(&legacy)==1);
    assert(legacy.stage==(known?2:3)&&legacy.platform_error==(known?-7:-9));
    assert(legacy.owner_tag==(known?123:456));
    puts("PASS 首次终局身份快照及旧 ABI 兼容");fflush(stdout);_Exit(0);
}
