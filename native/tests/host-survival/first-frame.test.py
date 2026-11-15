"""编译真实事件通知分支：配置变化不能冒充首帧，播放重启只通知一次。"""
from pathlib import Path
import tempfile,subprocess
root=Path(__file__).resolve().parents[3];s=(root/'packages/vidall-player/src/main/cpp/napi_init.cpp').read_text()
start=s.index('            if (event->event_id == MPV_EVENT_VIDEO_RECONFIG)') if '            if (event->event_id == MPV_EVENT_VIDEO_RECONFIG)' in s else s.index('            if (renderBackend_ == vidall::render::RenderBackend::Vulkan &&')
begin=s.index('{',start);i=begin+1;depth=1
while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
block=s[start:i]
code=r'''
#include "render_backend_policy.h"
#include <atomic>
#include <cassert>
#include <cstring>
enum{MPV_EVENT_VIDEO_RECONFIG,MPV_EVENT_PLAYBACK_RESTART,MPV_EVENT_END_FILE};
struct Event{int event_id;};
struct Harness {
 std::atomic<bool> firstFrameSent_{false};int delivered=0;
 vidall::render::RenderBackend renderBackend_=vidall::render::RenderBackend::Vulkan;
 void Dispatch(const char*k,const char*v){assert(!strcmp(k,"state")&&!strcmp(v,"playing"));delivered++;}
 void receive(int id){Event e{id};auto*event=&e;/* BLOCK */}
};
int main(){
 Harness h;h.receive(MPV_EVENT_VIDEO_RECONFIG);h.receive(MPV_EVENT_VIDEO_RECONFIG);assert(h.delivered==0);
 h.receive(MPV_EVENT_END_FILE);assert(h.delivered==0); // 初始化失败不发首帧。
 h.receive(MPV_EVENT_PLAYBACK_RESTART);assert(h.delivered==1);
 h.receive(MPV_EVENT_PLAYBACK_RESTART);h.receive(MPV_EVENT_VIDEO_RECONFIG);assert(h.delivered==1); // seek/尺寸变化不重复。
 h.firstFrameSent_=false;h.receive(MPV_EVENT_PLAYBACK_RESTART);assert(h.delivered==2); // 新视频。
 Harness sw;sw.renderBackend_=vidall::render::RenderBackend::Software;
 sw.receive(MPV_EVENT_VIDEO_RECONFIG);sw.receive(MPV_EVENT_PLAYBACK_RESTART);assert(sw.delivered==0); // 软件路径由真实渲染循环通知。
}
'''.replace('/* BLOCK */',block)
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(code);subprocess.run(['clang++','-std=c++17','-I'+str(root/'native/render'),str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('PASS Vulkan重启就绪首帧/重配置不误发/新片一次/seek去重/软件路径独立')
