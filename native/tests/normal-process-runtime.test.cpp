#include "process_runtime.h"
#include <mpv/ohcodec_terminal.h>
#include <libavformat/ohcodec_smb_runtime.h>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <thread>
#include <chrono>
#include <sys/stat.h>
#include <unistd.h>
#include <fstream>
static std::atomic<bool> terminal{false};
static int registrations=0, configurations=0, enables=0;
static int failure=0;
extern "C" uint32_t mpv_ohcodec_terminal_api_version(){return failure==1?0:MPV_OHCODEC_TERMINAL_ABI_VERSION;}
extern "C" int mpv_ohcodec_terminal_register(const mpv_ohcodec_terminal_config*){registrations++;return failure==2?-1:0;}
extern "C" int mpv_ohcodec_terminal_enable(){enables++;return failure==3?-1:0;}
extern "C" int mpv_ohcodec_terminal_snapshot(mpv_ohcodec_terminal_record*r){if(!terminal)return 0;r->platform_error=-4;r->stage=1;r->owner_tag=7;return 1;}
extern "C" int ohcodec_smb_runtime_configure_v1(const struct ohcodec_smb_runtime_v1*){configurations++;return failure==4?-1:0;}
int main(int argc,char**argv){
 assert(argc==3);std::string mode=argv[1],root=argv[2];mkdir(root.c_str(),0700);
 if(mode=="no-policy"){assert(std::string(vidall::runtime::AdmissionError())=="RUNTIME_NOT_READY");assert(!registrations);puts("PASS");return 0;}
 if(mode=="abi")failure=1;if(mode=="register")failure=2;if(mode=="enable")failure=3;if(mode=="smb")failure=4;
 const std::string config="[global]\nclient min protocol = SMB2_02\n";

 if(mode=="invalid-config"||mode=="invalid-deadline"){
  auto rc=vidall::runtime::Configure(root,mode=="invalid-config"?"bad":config,mode=="invalid-deadline"?999:1000);
  assert(rc&&std::string(rc)=="RUNTIME_CONFIG_INVALID");assert(vidall::runtime::Snapshot().state==0);assert(!configurations&&!registrations&&!enables);puts("PASS");return 0;
 }
 if(mode=="resources-rejected"){
  vidall::runtime::RejectResources();assert(vidall::runtime::Snapshot().state==3);assert(vidall::runtime::AdmissionError());assert(vidall::runtime::Configure(root,config,1000));assert(!configurations&&!registrations&&!enables);puts("PASS");return 0;
 }
 bool resourceFailure=mode=="directory-missing"||mode=="directory-file"||mode=="directory-symlink"||mode=="config-corrupt";
 if(mode=="directory-missing")root+="/missing-parent";
 if(mode=="directory-file"){root+="/not-directory";std::ofstream(root)<<"file";}
 if(mode=="directory-symlink"){auto target=root+"/target";mkdir(target.c_str(),0700);assert(!symlink(target.c_str(),(root+"/vidall-runtime-v1").c_str()));}
 if(mode=="config-corrupt"){mkdir((root+"/vidall-runtime-v1").c_str(),0700);std::ofstream(root+"/vidall-runtime-v1/smb.conf")<<"bad configuration";}
 auto rc=vidall::runtime::Configure(root,config,1000);
 if(resourceFailure){assert(rc&&std::string(rc)=="RUNTIME_RESOURCE_FAILED");assert(vidall::runtime::Snapshot().state==3);assert(vidall::runtime::AdmissionError());assert(!configurations&&!registrations&&!enables);auto second=vidall::runtime::Configure(root,config,1000);assert(second&&std::string(second)==rc);puts("PASS");return 0;}

 if(failure){assert(rc);assert(vidall::runtime::AdmissionError());assert(vidall::runtime::Snapshot().state==3);
  auto error=std::string(rc);int oldRegisters=registrations,oldConfig=configurations,oldEnables=enables;failure=0;
  auto retry=vidall::runtime::Configure(root,config,1000);assert(retry&&std::string(retry)==error);assert(registrations==oldRegisters&&configurations==oldConfig&&enables==oldEnables);
  auto conflict=vidall::runtime::Configure(root,config,2000);assert(conflict&&std::string(conflict)=="RUNTIME_CONFIG_CONFLICT");puts("PASS");return 0;}
 assert(!rc);assert(!vidall::runtime::AdmissionError());
 assert(!vidall::runtime::Configure(root,config,1000));assert(registrations==1&&configurations==1&&enables==1);
 assert(vidall::runtime::Configure(root,config,2000));
 if(mode=="deadline"){
  terminal=true;auto first=vidall::runtime::Snapshot();assert(first.state==4);
  std::this_thread::sleep_for(std::chrono::milliseconds(200));auto again=vidall::runtime::Snapshot();assert(first.firstObservedMs==again.firstObservedMs);
  for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));
 }
 assert(mode=="normal");puts("PASS");return 0;
}
