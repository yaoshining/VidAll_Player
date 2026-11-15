# T063：已停止音频与释放挂起的最小修复

## 已复现与修复

真实`release_for_recovery`在调用Release前没有保存平台已经STOPPED的事实。若Release长期不返回，同时发生全局终局，旧槽仍被计入`audio_pending`，即使音频已停止也无法放行兼容代。T063回归用真实函数、平台替身复现原断言失败，原始日志保留在`/tmp/vidall-t063-release-red.log`；不将替身当作真机永久故障。

新增0013补丁：已撤销回调、停妥时钟采样线程，在`mp_host_audio_remove`持有的同一控制锁内，只读查询状态；仅明确STOPPED才发布静止。Release失败或未知仍保留原renderer、AO、线程和资源槽；不会并发Start/Release、强制取消或复位终局。迟到Release成功才回收预算。RUNNING、PAUSED、PREPARED、查询错误与查询尚未返回均不提前放行。

状态查询接口自API10提供，API19可用，见[官方OHAudio接口](https://developer.huawei.com/consumer/en/doc/harmonyos-references/capi-native-audiorenderer-h/)。这不是仅API19路径的缺陷。没有新增PCM队列、音频补偿或自动退出；尺寸、旋转、EOF、焦点逻辑与FFmpeg库未变。

## 验证分层

- 19个实际生命周期函数场景通过，新增7个已停止/未知、Release失败/阻塞、查询失败/阻塞、迟到完成场景；含剩余15槽与第17次申请拒绝检查。
- 27个API19/24/26时钟替身场景通过；94项宿主门禁与来源审计通过。
- 本地MacBook Pro ARM64完成mpv新核心及完整HAR构建。libmpv SHA256：`f57068665298079682f9d90b0b13ae8ac427c844a3debf4b47cd7107611d5a82`。FFmpeg六库及C++运行库不变。最终HAR仍须来自iMac Actions，不把本地构建当交付。
- 新核心的目标设备和全局诊断尚在推进，不能沿用旧核心结果宣称已完成。

## 仍未解决

未知Stop/Release不返回、状态查询自身卡住时，仍不能证明旧声音已停止；16槽全部被未知调用占用时仍不保证续播。此次仅修复“已有停止事实被资源释放等待遮蔽”的误阻挡。不能把单流超时、槽耗尽或OHCodec终局当成系统整体音频故障；没有新增退出路径。

S32→T063→0013→生命周期回归/来源锁可追踪。宪章检查通过源码与宿主层；设备、CI及最终交付是未完成项而非例外。Todoist第3/4项继续开放。
