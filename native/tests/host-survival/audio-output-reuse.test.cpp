// 健康输出复用协议原型；没有平台驱动接入，不能当作设备通过。
#include "../../experimental/audio_output_reuse.h"
#include <cassert>
#include <array>
#include <thread>
using vidall::experimental::AudioOutputReuse;
int main() {
  AudioOutputReuse out({48000,4,1,1,3});
  std::array<unsigned char,16> old; old.fill(0x11);
  std::array<unsigned char,16> next; next.fill(0x22);
  std::array<unsigned char,16> got;
  auto token=out.Attach({48000,4,1,1,3}); assert(token);
  assert(out.Write(token,old.data(),4));
  assert(out.Callback(got.data(),4)==4 && got==old);
  assert(out.Retire(token)); // 已送平台4帧，未送的帧可以清除，已送的不能假报已停止。
  assert(!out.Attach({48000,4,1,1,3}));
  assert(!out.ConfirmDrain(1,3));
  assert(!out.ConfirmDrain(2,4)); // 路由/时钟域不是同一次。
  assert(out.ConfirmDrain(1,4));
  assert(!out.Attach({44100,4,1,1,3}));
  assert(!out.Attach({48000,8,1,1,3}));
  assert(!out.Attach({48000,4,2,1,3}));
  assert(!out.Attach({48000,4,1,1,12})); // 同字节数但声道顺序不同也不能复用。
  auto fresh=out.Attach({48000,4,1,1,3}); assert(fresh && fresh!=token);
  assert(!out.Write(token,old.data(),4)); assert(!out.Retire(token));
  assert(out.Write(fresh,next.data(),4));
  assert(out.DelayFrames(fresh,1,4)==4); // 软件队列尚未送平台，必须计入时钟。
  assert(out.Callback(got.data(),4)==4 && got==next);
  assert(out.DelayFrames(fresh,1,4)==4); // 已送平台但尚未播放，仍是延迟。
  assert(out.DelayFrames(fresh,1,8)==0);
  assert(out.DelayFrames(fresh,2,8)==-1);
  assert(out.Retire(fresh)); assert(out.ConfirmDrain(1,8));
  // 千次换源复用同一个所有者，不积累renderer/线程；假设真实平台排空确认持续可用。
  uint64_t cursor=8;
  for(int i=0;i<1000;i++) {
    auto t=out.Attach({48000,4,1,1,3}); assert(t);
    std::thread late([&]{for(int j=0;j<100;j++)assert(!out.Write(token,old.data(),4));});
    // try-lock允许有限重试；测试不把Busy当作静音已完成。
    while(!out.Write(t,next.data(),4)) std::this_thread::yield();
    late.join();
    assert(out.Callback(got.data(),4)==4 && got==next);cursor+=4;
    assert(out.Retire(t)); assert(out.ConfirmDrain(1,cursor));
  }
  auto t=out.Attach({48000,4,1,1,3}); assert(t);
  std::array<unsigned char,8192> full; full.fill(0x33);
  assert(out.Write(t,full.data(),2048)); assert(!out.Write(t,next.data(),1));
  assert(out.Retire(t)); // 丢弃未提交的软件队列，拒绝旧生产者，无平台调用。
  assert(out.ConfirmDrain(1,cursor));
  t=out.Attach({48000,4,1,1,3});assert(t);
  got.fill(0x77); assert(out.Callback(got.data(),4)==0);
  for(auto b:got)assert(!b); // 欠载只填零。
  assert(out.Retire(t));assert(out.ConfirmDrain(1,cursor+4));
  AudioOutputReuse invalid({48000,33,1,1,3});
  got.fill(0x77); assert(!invalid.Callback(got.data(),1));
  for(auto b:got)assert(b==0x77);
  AudioOutputReuse nonpcm({48000,4,99,1,3});assert(!nonpcm.Attach({48000,4,99,1,3}));
  out.Invalidate(); assert(!out.Attach({48000,4,1,1,3}));
  assert(!out.ConfirmDrain(1,UINT64_MAX));
}
