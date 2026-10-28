#include "process_runtime.h"
#if VIDALL_MPV_AVAILABLE
#include <mpv/ohcodec_terminal.h>
#include <libavformat/ohcodec_smb_runtime.h>
#include <atomic>
#include <mutex>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
namespace vidall::runtime {
namespace {
std::atomic<int> state{0};
std::atomic<std::int64_t> firstAt{0};
std::atomic<unsigned> deadline{0};
std::atomic<const char*> failureCode{nullptr};
std::mutex configureMutex;
std::string configuredRoot;
std::string configuredText;
mpv_ohcodec_terminal_record record{};
std::atomic_flag recordWriter=ATOMIC_FLAG_INIT;
std::int64_t Now(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
void Observe(){
 if(firstAt.load(std::memory_order_acquire)||state.load(std::memory_order_acquire)<2)return;
 mpv_ohcodec_terminal_record r{};r.size=sizeof(r);r.abi_version=MPV_OHCODEC_TERMINAL_ABI_VERSION;
 if(mpv_ohcodec_terminal_snapshot(&r)!=1)return;
 // 不等待其他观察者；首个写者按 release 发布完整快照。
 if(recordWriter.test_and_set(std::memory_order_acquire))return;
 record=r;firstAt.store(Now(),std::memory_order_release);state.store(4,std::memory_order_release);
}
void Receiver(const mpv_ohcodec_terminal_record*,void*){}
void Monitor(){for(;;){if(state.load(std::memory_order_acquire)==3)return;Observe();auto first=firstAt.load(std::memory_order_acquire);if(first&&Now()-first>=deadline.load())std::_Exit(86);std::this_thread::sleep_for(std::chrono::milliseconds(10));}}
bool Directory(const std::string&p,bool create){
 struct stat s{};
 if(lstat(p.c_str(),&s)){if(!create||mkdir(p.c_str(),0700))return false;if(lstat(p.c_str(),&s))return false;}
 return S_ISDIR(s.st_mode)&&access(p.c_str(),R_OK|W_OK|X_OK)==0;
}
bool Prepare(const std::string&root,const std::string&text){
 if(root.empty()||root[0]!='/'||root.find("/../")!=std::string::npos||!Directory(root,false))return false;
 const std::string p=root+"/vidall-runtime-v1";
 for(const char*s:{"","/state","/state/private","/state/state","/state/lock","/cache","/cache/demux","/resources"})if(!Directory(p+s,true))return false;
 const std::string file=p+"/smb.conf";
 int fd=open(file.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
 if(fd>=0){size_t done=0;while(done<text.size()){ssize_t n=write(fd,text.data()+done,text.size()-done);if(n<=0){close(fd);return false;}done+=n;}return close(fd)==0;}
 fd=open(file.c_str(),O_RDONLY|O_NOFOLLOW);if(fd<0)return false;
 char b[256];ssize_t n=read(fd,b,sizeof(b));close(fd);return n==static_cast<ssize_t>(text.size())&&!memcmp(b,text.data(),text.size());
}
}
const char* Configure(const std::string&filesDir,const std::string&config,unsigned ms){
 if(ms<1000||ms>10000||config!="[global]\nclient min protocol = SMB2_02\n")return "RUNTIME_CONFIG_INVALID";
 std::lock_guard<std::mutex>lock(configureMutex);
 if(state.load()!=0){if(configuredRoot!=filesDir||configuredText!=config||deadline.load()!=ms)return "RUNTIME_CONFIG_CONFLICT";if(state.load()==2)return nullptr;if(state.load()==4)return "PLAYER_TERMINAL";return failureCode.load()?failureCode.load():"RUNTIME_NOT_READY";}
 state=1;configuredRoot=filesDir;configuredText=config;deadline=ms;
 auto fail=[](const char*code){failureCode.store(code);state.store(3,std::memory_order_release);return code;};
 if(!Prepare(filesDir,config))return fail("RUNTIME_RESOURCE_FAILED");
 if(mpv_ohcodec_terminal_api_version()!=MPV_OHCODEC_TERMINAL_ABI_VERSION)return fail("RUNTIME_ABI_MISMATCH");
 const auto root=filesDir+"/vidall-runtime-v1";
 const auto file=root+"/smb.conf",s=root+"/state",c=root+"/cache",r=root+"/resources";
 ohcodec_smb_runtime_v1 smb{sizeof(smb),file.c_str(),s.c_str(),c.c_str(),r.c_str()};
 if(ohcodec_smb_runtime_configure_v1(&smb))return fail("RUNTIME_SMB_FAILED");
 mpv_ohcodec_terminal_config t{};t.size=sizeof(t);t.abi_version=MPV_OHCODEC_TERMINAL_ABI_VERSION;t.handler=Receiver;
 if(mpv_ohcodec_terminal_register(&t))return fail("RUNTIME_TERMINAL_REGISTER_FAILED");
 try{std::thread(Monitor).detach();}catch(...){return fail("RUNTIME_MONITOR_FAILED");}
 if(mpv_ohcodec_terminal_enable())return fail("RUNTIME_TERMINAL_ENABLE_FAILED");
 state.store(2,std::memory_order_release);return nullptr;
}
void RejectResources(){int expected=0;if(state.compare_exchange_strong(expected,1)){failureCode.store("RUNTIME_RESOURCE_FAILED");state.store(3,std::memory_order_release);}}
Status Snapshot(){
 Observe();Status s{};s.state=state.load(std::memory_order_acquire);s.deadlineMs=deadline.load();s.firstObservedMs=firstAt.load(std::memory_order_acquire);
 if(s.firstObservedMs){s.state=4;s.platformError=record.platform_error;s.stage=record.stage;s.ownerTag=record.owner_tag;}return s;
}
const char* AdmissionError(){auto s=Snapshot();return s.state==4?"PLAYER_TERMINAL":s.state==2?nullptr:"RUNTIME_NOT_READY";}
void ParkIfTerminal(){if(Snapshot().state==4)for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}
}

#else
namespace vidall::runtime {
const char* Configure(const std::string&,const std::string&,unsigned){return "FEATURE_UNSUPPORTED";}
Status Snapshot(){return {0,0,0,0,0,0};}
void RejectResources(){}
const char* AdmissionError(){return "FEATURE_UNSUPPORTED";}
void ParkIfTerminal(){}
}
#endif
