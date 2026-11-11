"""将 NAPI 桥与 mpv 依赖按 RTLD_LOCAL 加载，验证恢复接口不依赖全局命名空间。"""
from pathlib import Path
import ctypes, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 (p/'core.cpp').write_text(r'''
#include "host_recovery_api.h"
#include <mpv/ohcodec_terminal.h>
#include <libavformat/ohcodec_smb_runtime.h>
extern "C" {
uint32_t mpv_ohcodec_terminal_api_version(){return MPV_OHCODEC_TERMINAL_ABI_VERSION;}
int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config*){return 0;}
int mpv_ohcodec_terminal_enable(){return 0;}
int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*){return 0;}
int ohcodec_smb_runtime_configure_v1(const ohcodec_smb_runtime_v1*){return 0;}
uint32_t mpv_host_recovery_api_version(){return MPV_HOST_RECOVERY_ABI_VERSION;}
uint64_t mpv_host_recovery_generation(){return 1;}
unsigned mpv_host_recovery_audio_pending(){return 0;}
void mpv_host_recovery_stop_audio(){}
int mpv_host_loadfile_async(mpv_handle*,uint64_t,uint64_t,const char**){return 0;}
int mpv_host_fault_snapshot(mpv_host_fault_record*){return 0;}
}
''')
 (p/'bridge.cpp').write_text('''#include "process_runtime.h"
#include <dlfcn.h>
extern "C" void* TestDlsym(void* handle,const char* name) { return handle==RTLD_DEFAULT?nullptr:dlsym(handle,name); }
extern "C" const char* configure_local(const char* path) {
return vidall::runtime::Configure(path,"[global]\\nclient min protocol = SMB2_02\\n",1000,vidall::runtime::TerminalPolicy::PreserveHost);
}
''')
 flags=['clang++','-std=c++17','-shared','-fPIC','-pthread','-DVIDALL_MPV_AVAILABLE=1','-I'+str(root/'native/runtime'),'-I'+str(root/'native/mpv'),'-I'+str(root/'release/inputs/004-normal-core/include')]
 subprocess.run(flags+[str(p/'core.cpp'),'-o',str(p/'libmpv.so')]+(['-Wl,-install_name,'+str(p/'libmpv.so')] if sys.platform=='darwin' else []),check=True)
 subprocess.run(flags+['-Ddlsym=TestDlsym','-c',str(root/'native/runtime/process_runtime.cpp'),'-o',str(p/'runtime.o')],check=True)
 subprocess.run(flags+[str(p/'bridge.cpp'),str(p/'runtime.o'),'-L'+str(p),'-lmpv','-Wl,-rpath,'+str(p),'-o',str(p/'bridge.so')]+([] if sys.platform=='darwin' else ['-ldl']),check=True)
 # 子进程退出后才清理共享库，避免仍运行的 runtime 线程访问已卸载映像。
 subprocess.run([sys.executable,'-c',r'''
import ctypes,sys,os
lib=ctypes.CDLL(sys.argv[1],mode=ctypes.RTLD_LOCAL)
lib.configure_local.argtypes=[ctypes.c_char_p];lib.configure_local.restype=ctypes.c_char_p
error=lib.configure_local(sys.argv[2].encode())
assert error is None,error
os._exit(0)
''',str(p/'bridge.so'),str(p)],check=True,timeout=5)
print('PASS 局部加载的真实 runtime 解析同一 mpv 依赖的恢复 ABI')
