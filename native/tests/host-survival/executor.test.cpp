#include "session_isolation.h"
#include <cassert>
#include <future>
#include <vector>
using vidall::runtime::SessionIsolation;
using namespace std::chrono_literals;
int main(){
 using Pool=SessionIsolation::Pool;
 auto configuration=SessionIsolation::Acquire(Pool::Runtime);
 assert(configuration&&!SessionIsolation::Acquire(Pool::Runtime));
 std::vector<std::shared_ptr<SessionIsolation>> ordinary;
 for(int i=0;i<6;i++){auto s=SessionIsolation::Acquire(Pool::Standard);assert(s);ordinary.push_back(s);}
 assert(!SessionIsolation::Acquire(Pool::Standard));
 auto compatibility=SessionIsolation::Acquire(Pool::Compatible);
 auto spare=SessionIsolation::Acquire(Pool::Compatible);
 assert(compatibility&&spare&&!SessionIsolation::Acquire(Pool::Compatible));
 auto recovery=SessionIsolation::Acquire(Pool::Recovery);
 auto recoverySpare=SessionIsolation::Acquire(Pool::Recovery);
 assert(recovery&&recoverySpare&&!SessionIsolation::Acquire(Pool::Recovery));
 assert(recovery->Run([]{},200ms));
 assert(!SessionIsolation::Acquire(Pool::Compatible));
 auto hardware=SessionIsolation::Acquire();assert(hardware);
 std::promise<void> unblock,entered;
 auto gate=unblock.get_future().share();
 auto pending=std::async(std::launch::async,[&]{return ordinary[0]->Run([&]{entered.set_value();gate.wait();},30ms);});
 entered.get_future().wait();assert(!pending.get());
 assert(compatibility->Run([]{},200ms));
 assert(!SessionIsolation::Acquire(Pool::Standard));
 ordinary[0].reset(); // 实际线程还在执行时，不能归还额度。
 assert(!SessionIsolation::Acquire(Pool::Standard));
 unblock.set_value();
 std::shared_ptr<SessionIsolation> replacement;
 for(int i=0;i<1000&&!replacement;i++){
  replacement=SessionIsolation::Acquire(Pool::Standard);
  if(!replacement)std::this_thread::sleep_for(1ms);
 }
 assert(replacement&&replacement->Run([]{},200ms));
 // 兼容池只有两个名额：两次关闭都未返回时，第三个播放器也不能无限创建。
 std::promise<void> firstClose,secondClose,firstEntered,secondEntered;
 auto firstGate=firstClose.get_future().share(),secondGate=secondClose.get_future().share();
 auto closing1=std::async(std::launch::async,[&]{return compatibility->Run([&]{firstEntered.set_value();firstGate.wait();},30ms,true);});
 auto closing2=std::async(std::launch::async,[&]{return spare->Run([&]{secondEntered.set_value();secondGate.wait();},30ms,true);});
 firstEntered.get_future().wait();secondEntered.get_future().wait();
 assert(!closing1.get()&&!closing2.get());
 compatibility.reset();spare.reset();assert(!SessionIsolation::Acquire(Pool::Compatible));
 firstClose.set_value();
 std::shared_ptr<SessionIsolation> afterLateClose;
 for(int i=0;i<1000&&!afterLateClose;i++) {
  afterLateClose=SessionIsolation::Acquire(Pool::Compatible);
  if(!afterLateClose)std::this_thread::sleep_for(1ms);
 }
 assert(afterLateClose&&afterLateClose->Run([]{},200ms));
 assert(!SessionIsolation::Acquire(Pool::Compatible));
 secondClose.set_value();

}
