#include "process_runtime.h"
#include <mpv/ohcodec_terminal.h>
#include <libavformat/ohcodec_smb_runtime.h>
#include <atomic>
#include <cassert>
#include <chrono>
#include <thread>
#include <sys/stat.h>
#include <string>
static std::atomic<bool> terminal{false},retired{false},allowStop{false},stopped{false};
static unsigned version=0x10000;
extern "C" {
uint32_t mpv_ohcodec_terminal_api_version(){return MPV_OHCODEC_TERMINAL_ABI_VERSION;}
int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config*){return 0;}
int mpv_ohcodec_terminal_enable(){return 0;}
int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*r){if(!terminal)return 0;r->stage=1;r->platform_error=-4;return 1;}
int ohcodec_smb_runtime_configure_v1(const ohcodec_smb_runtime_v1*){return 0;}
#ifndef NO_RECOVERY_ABI
uint32_t mpv_host_recovery_api_version(){return version;}
uint64_t mpv_host_recovery_generation(){return retired?2:1;}
unsigned mpv_host_recovery_audio_pending(){return stopped?0:1;}
void mpv_host_recovery_stop_audio(){while(!allowStop)std::this_thread::sleep_for(std::chrono::milliseconds(1));stopped=true;}
#endif
}
int main(int argc,char**argv){
 assert(argc==3);mkdir(argv[2],0700);
 if(std::string(argv[1])=="abi")version=0;
 auto rc=vidall::runtime::Configure(argv[2],"[global]\nclient min protocol = SMB2_02\n",1000,vidall::runtime::TerminalPolicy::PreserveHost);
#ifdef NO_RECOVERY_ABI
 version=0;
#endif
 if(version==0){assert(rc&&std::string(rc)=="RUNTIME_RECOVERY_UNAVAILABLE");return 0;}
 assert(!rc);assert(!vidall::runtime::AdmissionError());
 const auto oldGeneration=vidall::runtime::CaptureGeneration();
 assert(oldGeneration==1);
 assert(!vidall::runtime::SessionAdmissionError(oldGeneration,false));
 assert(!vidall::runtime::SessionAdmissionError(oldGeneration,true));
 assert(vidall::runtime::Configure(argv[2],"[global]\nclient min protocol = SMB2_02\n",1000));
 retired=true;assert(vidall::runtime::CaptureGeneration()==0);
 assert(vidall::runtime::SessionAdmissionError(oldGeneration,true));
 terminal=true;assert(vidall::runtime::Snapshot().state==4);
 assert(vidall::runtime::AdmissionError(true));
 assert(vidall::runtime::CaptureGeneration()==0);
 assert(vidall::runtime::SessionAdmissionError(oldGeneration,true));
 // 旧截止时间的三倍，平台 Stop 悬挂仍不退出，快照/准入不等待该 Stop。
 std::this_thread::sleep_for(std::chrono::milliseconds(3100));
 assert(vidall::runtime::Snapshot().recoveryState==3);
 assert(vidall::runtime::AdmissionError(true));assert(vidall::runtime::AdmissionError());
 allowStop=true;
 for(int i=0;i<1000&&vidall::runtime::AdmissionError(true);i++)std::this_thread::sleep_for(std::chrono::milliseconds(1));
 assert(!vidall::runtime::AdmissionError(true));assert(vidall::runtime::AdmissionError());
 const auto newGeneration=vidall::runtime::CaptureGeneration();
 assert(newGeneration==2);
 assert(!vidall::runtime::SessionAdmissionError(newGeneration,true));
 assert(vidall::runtime::SessionAdmissionError(newGeneration,false));
 assert(vidall::runtime::SessionAdmissionError(oldGeneration,true));
 assert(vidall::runtime::SessionAdmissionError(0,true));
 assert(vidall::runtime::SessionAdmissionError(3,true));
 vidall::runtime::ParkIfTerminal(true);
 assert(vidall::runtime::Snapshot().state==4); // 硬解终局永不复位。
}
