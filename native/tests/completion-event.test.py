#!/usr/bin/env python3
"""编译实际 NAPI 类的 completion 方法；仅替换 NAPI 投递，覆盖媒体身份交错。"""
import pathlib,subprocess,tempfile,os,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
source=pathlib.Path(os.environ.get('NATIVE_COMPLETION_SOURCE',ROOT/'packages/vidall-player/src/main/cpp/napi_init.cpp')).read_text()
def method(name):
    at=source.index('    '+name);start=source.index('{',at);depth=1;i=start+1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[at:i]
names=['std::uint64_t BeginCompletion()', 'void InvalidateCompletion()', 'void CompletionReply(', 'void CompleteFile(', 'void DispatchCompletion(']
legacy='--legacy-red' in sys.argv
methods='' if legacy else '\n'.join(method(n) for n in names)
start=source.index('            if (event->event_id == MPV_EVENT_END_FILE) {');begin=source.index('{',start);depth=1;i=begin+1
while depth:depth+=(source[i]=='{')-(source[i]=='}');i+=1
end_block=source[start:i]
fields=sorted(set(re.findall(r'\b([A-Za-z]\w*_)\s*(?:=|\.clear)',end_block)))
fields=[f for f in fields if f not in ['completionEpoch_','eventEpoch_','generation_','released_']]
extras='struct Field {void clear(){};template<class T> Field& operator=(T){return *this;}};'+''.join('Field '+f+';' for f in fields)
load=source[source.index('        const char* command[] = {"loadfile"'):source.index('    NativeResult Play(')]
load=load[:load.rfind('    }')]
load='struct NativeResult {bool ok;uint64_t handle;const char* error;}; NativeResult load(){std::string uri="same://input";uint64_t handle=1;'+load+'}'
reply_line=''
if not legacy:
    reply_line=re.search(r'if \(event->event_id == MPV_EVENT_COMMAND_REPLY\) CompletionReply\(\*event\);',source).group(0)
    stop=method('NativeResult Stop(')
    release=method('void Release()')
    assert stop.index('InvalidateCompletion();') < stop.index('mpv_command_async(')
    assert release.index('InvalidateCompletion();') < release.index('released_ = true;') < release.index('eventThread_.join()')


code=r'''
#include <atomic>
#include <mutex>
#include <vector>
#include <algorithm>
#include <string>
#include <cstring>
#include <cassert>
#include <thread>
#include <condition_variable>
#include <chrono>
struct Handle {void* get(){return nullptr;}};
struct Event {std::string type,message;uint64_t epoch,sequence,generation;};
static constexpr int napi_tsfn_nonblocking=0,napi_ok=0;
static uint64_t requested=0;static int submitResult=0;
static int test_command_async(void*,uint64_t userdata,const char**){requested=userdata;return submitResult;}
#define mpv_command_async test_command_async
#include <mpv/client.h>
namespace vidall { namespace runtime { std::atomic<bool> terminal{false};const char* AdmissionError(){return terminal?"terminal":nullptr;} } }
class Harness {
public:
std::mutex completionMutex_,callbackMutex_,lifecycleMutex_;void* eventTsfn_=this;bool rendererReady_=true;std::atomic<uint64_t> eventEpoch_{0},generation_{1},eventSequence_{0};std::atomic<bool> released_{false};
uint64_t completionEpoch_=0,completionGeneration_=0;int64_t completionEntry_=-1;bool completionReplied_=false;std::vector<int64_t> completionEnded_;
Handle player_;bool diagnosticsStopped_=false,firstFrameSent_=false; EXTRAS
std::vector<std::pair<uint64_t,uint64_t>> sent;std::mutex testMutex;std::condition_variable cv;bool block=false,entered=false,unblock=false;
void Dispatch(const std::string& type,const std::string& message){if(type=="state"&&message=="completed")sent.push_back({eventEpoch_,generation_});}
LOAD
@@STOP@@
void process(mpv_event* event){@@REPLY@@ @@END_BLOCK@@}

int napi_call_threadsafe_function(void*,Event* event,int){std::unique_lock<std::mutex> lk(testMutex);if(block){entered=true;cv.notify_all();cv.wait(lk,[&]{return unblock;});}sent.push_back({event->epoch,event->generation});delete event;return napi_ok;}
METHODS
void reply(uint64_t request,int64_t id,int error=0){mpv_node value{};value.format=MPV_FORMAT_INT64;value.u.int64=id;char key[]="playlist_entry_id";char* keys[]={key};mpv_node_list list{1,&value,keys};mpv_event_command command{};command.result.format=MPV_FORMAT_NODE_MAP;command.result.u.list=&list;mpv_event event{};event.event_id=MPV_EVENT_COMMAND_REPLY;event.reply_userdata=request;event.error=error;event.data=&command;process(&event);}
void end(int64_t id,int reason=MPV_END_FILE_REASON_EOF){mpv_event_end_file end{};end.reason=static_cast<mpv_end_file_reason>(reason);end.playlist_entry_id=id;mpv_event event{};event.event_id=MPV_EVENT_END_FILE;event.data=&end;process(&event);}
};
int main(){
 {Harness h;h.load();assert(requested==h.eventEpoch_&&requested>0);h.reply(requested,10);h.end(10);assert(h.sent.size()==1);}
 {Harness h;submitResult=-1;h.load();submitResult=0;h.reply(requested,10);h.end(10);assert(h.sent.empty());}
 {Harness h;auto old=h.BeginCompletion();h.reply(old,10);h.block=true;std::thread eof([&]{h.end(10);});{std::unique_lock<std::mutex> lk(h.testMutex);h.cv.wait(lk,[&]{return h.entered;});}std::atomic<bool> began{false},finished{false};std::thread loading([&]{began=true;h.BeginCompletion();finished=true;});while(!began)std::this_thread::yield();assert(!finished);{std::lock_guard<std::mutex> lk(h.testMutex);h.unblock=true;}h.cv.notify_all();eof.join();loading.join();assert(h.sent.size()==1&&h.sent[0].first==old&&h.eventEpoch_!=old);}

 {Harness h;auto e=h.BeginCompletion();h.reply(e,10);h.end(10);h.end(10);assert(h.sent.size()==1&&h.sent[0].first==e);}
 for(int reason:std::vector<int>{MPV_END_FILE_REASON_STOP,MPV_END_FILE_REASON_QUIT,MPV_END_FILE_REASON_ERROR,MPV_END_FILE_REASON_REDIRECT,99}){Harness h;auto e=h.BeginCompletion();h.reply(e,10);h.end(10,reason);h.end(10);assert(h.sent.empty());}
 {Harness h;auto old=h.BeginCompletion();h.reply(old,10);auto next=h.BeginCompletion();h.reply(old,10);h.reply(next,11);h.end(10);assert(h.sent.empty());h.end(11);assert(h.sent.size()==1&&h.sent[0].first==next);}
 {Harness h;auto e=h.BeginCompletion();h.end(10);h.reply(e,10);h.end(10);assert(h.sent.empty());}
 {Harness h;auto e=h.BeginCompletion();h.reply(e,10);h.Stop(1);h.end(10);assert(h.sent.empty());}
 for(int mode=0;mode<4;mode++){Harness h;auto e=h.BeginCompletion();h.reply(e,10);if(mode==0)h.InvalidateCompletion();if(mode==1)h.released_=true;if(mode==2)h.generation_=2;if(mode==3)vidall::runtime::terminal=true;h.end(10);assert(h.sent.empty());vidall::runtime::terminal=false;}
 for(int mode=0;mode<6;mode++){Harness h;auto e=h.BeginCompletion();mpv_node values[2]{};for(auto &v:values){v.format=MPV_FORMAT_INT64;v.u.int64=10;}char key[]="playlist_entry_id";char* keys[]={key,key};mpv_node_list list{mode==3?2:1,values,keys};mpv_event_command c{};c.result.format=mode==2?MPV_FORMAT_STRING:MPV_FORMAT_NODE_MAP;c.result.u.list=&list;mpv_event event{};event.reply_userdata=e;event.error=mode==0?-1:0;event.data=mode==1?nullptr:&c;if(mode==4)values[0].format=MPV_FORMAT_DOUBLE;if(mode==5)values[0].u.int64=-1;h.CompletionReply(event);h.reply(e,10);h.end(10);assert(h.sent.empty());}
 {Harness h;auto e=h.BeginCompletion();h.reply(e,10);std::thread t([&]{h.InvalidateCompletion();});t.join();h.end(10);assert(h.sent.empty());}
}
'''.replace('METHODS',methods).replace('EXTRAS',extras).replace('LOAD',load).replace('@@STOP@@',stop if not legacy else '').replace('@@REPLY@@',reply_line).replace('@@END_BLOCK@@',end_block)
if legacy:
    # 原始生产END_FILE分支仅清缓存，不会投递completed；该断言应语义失败。
    before=code[:code.index('int main(){')]
    # baseline没有新增方法，去掉仅用于新实现的load/reply辅助。
    before=before[:before.index('struct NativeResult')]+'void process(mpv_event* event){'+end_block+'} };\n'
    code=before+'int main(){Harness h;mpv_event_end_file end{};end.reason=MPV_END_FILE_REASON_EOF;end.playlist_entry_id=10;mpv_event event{};event.event_id=MPV_EVENT_END_FILE;event.data=&end;h.process(&event);assert(h.sent.size()==1 && "normal EOF must deliver completed");}'
with tempfile.TemporaryDirectory(prefix='completion-contract-') as out:
 p=pathlib.Path(out);(p/'test.cpp').write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-pthread','-I'+str(ROOT/'release/inputs/004-normal-core/include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS actual Load/Stop/COMMAND_REPLY/END_FILE/DispatchCompletion (NAPI投递替身), Release源码顺序: EOF唯一、非EOF、reply身份/格式、重载、晚到、失效与线程交错')
