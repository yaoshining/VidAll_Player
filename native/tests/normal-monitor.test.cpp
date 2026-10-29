// 包含真实实现，仅平台函数替身；直接验证 Monitor 返回，不以无调用冒充无空转。
#include "../runtime/process_runtime.cpp"
#include <cassert>
#include <cstdio>
static bool enableFails = false;
static std::atomic<bool> fatal{false};
extern "C" uint32_t mpv_ohcodec_terminal_api_version(){return MPV_OHCODEC_TERMINAL_ABI_VERSION;}
extern "C" int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config*){return 0;}
extern "C" int mpv_ohcodec_terminal_enable(){return enableFails?-1:0;}
extern "C" int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*r){if(!fatal)return 0;r->platform_error=-4;r->stage=1;r->owner_tag=7;return 1;}
extern "C" int ohcodec_smb_runtime_configure_v1(const struct ohcodec_smb_runtime_v1*){return 0;}
int main(int argc,char**argv){
 assert(argc==3);std::string mode=argv[1];enableFails=mode=="enable-failed";
 fprintf(stderr,"NATIVE_ENTRY %lld\n",(long long)vidall::runtime::Now());
 auto error=vidall::runtime::Configure(argv[2],"[global]\nclient min protocol = SMB2_02\n",1000);
 if(enableFails){assert(error&&std::string(error)=="RUNTIME_TERMINAL_ENABLE_FAILED");fprintf(stderr,"BEFORE %d\n",vidall::runtime::state.load());vidall::runtime::Monitor();fprintf(stderr,"AFTER\n");puts("MONITOR_RETURNED");return 0;}
 assert(!error);
 if(mode=="normal"){std::this_thread::sleep_for(std::chrono::milliseconds(30));assert(vidall::runtime::Snapshot().state==2);puts("READY");return 0;}
 assert(mode=="deadline");fprintf(stderr,"TERMINAL_AT %lld\n",(long long)vidall::runtime::Now());fatal=true;for(;;)std::this_thread::sleep_for(std::chrono::milliseconds(10));
}
