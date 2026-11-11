# 当前接入阻塞核对

2026-11-11。用户判断成立：public/runtime.ets 的唯一 terminalPolicy 是 controlled-app-exit；原生 Configure 没有接收策略参数，Monitor 到期执行 std::_Exit(86)。原样主机测试链接真实 process_runtime.cpp，平台 terminal/SMB 函数为既有测试替身，正常场景退出 0，终局场景 1009 ms 退出 86。此结果不表示任意坏片都会触发退出，也不是真机验收。

## 剩余生产触发路径

1. `hwdec_ohcodec.c::ohcodec_owner_fault`：owner 未启用隔离，或 `hw->global->client_api` 不存在时直接进入全局终局。来源包括排空不安全、已有保留错误、逐帧交接失败及 vo_gpu_next 关闭时发现残留。现有 Player 的正常 Vulkan 硬解路径会开启隔离；名额不足时禁用硬解交互。因此不能把这个后备分支的存在说成正常 Player 会话已实测触发。
2. `hwdec_ohcodec_pl.c::ohcodec_interop_pl_init`：begin_creation 成功后，其他线程关闭全局创建入口，end_creation 返回 false；初始化失败清理与成功收尾都调用 terminal_enter(LATE)。诊断身份校验分支也存在同类调用，但生产 DIAGNOSTIC=false，不计该分支。此路径需要先发生全局终局，是竞态保护，不是独立的坏片触发器。
3. `ohcodec_terminal.c` 首次进入即永久设置 admission CLOSED，发布不可变 record 并让调用线程停留；没有安全 reset。snapshot/owner_tag 不是可恢复凭据，也不能通过再次 initialize 解除。

本轮检查的派生源码与实际 mpv 编译目录对应文件逐字节一致：ohcodec_terminal.c `f6bede79b265baa63d1e7c335a9cc6286b1d6da19268fb3eabd6c38be2482ee2`；hwdec_ohcodec.c `fa98e276939192bc23d21cdf44326851e93bf1b41296d470d532e665be0daa11`；hwdec_ohcodec_pl.c `a2fd944b1f9d9bca1801e7b4322e87d81b12c22c6a3e1f1e061d33f9cab2b002`。生产 libmpv 身份见已有 normal-compile-binding.json。

## 为什么不能只删退出计时器

Release/DestroyRenderer 及析构含 ParkIfTerminal；未持有 SessionIsolation 的工作在 NAPI execute 中直接运行。终局恰好发生于在途工作时，该工作可能长期不返回。现有 CleanupSessions 已同步关闭回调并保留终局对象，但它不等于终局一发生就关闭全部通道，也没有给全部软件实例和后台销毁线程设置总上限。两名额只约束受保护的硬解会话，不约束所有保留对象。

最初提出“全局终局后禁用 MPV，用户重启恢复”的候选已被用户拒绝，不是接受的契约。当前桥接实现不能继续播放，但此前把限制扩大到整个 MPV 软件核心的表述过宽：底层终局门直接保护 OHCodec interop，新代纯软件解码/渲染是否能够在保持硬解锁关闭时工作，需要单独验证。具体路线与未验证条件见 [恢复可行性核对](recovery-feasibility.md)，不能强行清除安全门，也不能提前声称恢复通过。

## 架构

交付 HAR SHA-256 `563eaffa04f01fbc2551c6362585a4d0d6254d5449d357508dad5e615d9f73d1` 只含 arm64-v8a 九库。deveco26 目标明确仅 ARM64。default 虽列出 x86_64，CMake 该分支设置 VIDALL_MPV_AVAILABLE=0，Configure/CreateSession 返回 FEATURE_UNSUPPORTED；不能用该探针宣称 x86_64 播放兼容。

可以明确交付 ARM64 播放核心；如消费端需要继续发布双架构，则必须另行安排 x86_64 完整依赖或具有显式能力协商的不可用实现，不能混用旧版桥。完整 x86_64 FFmpeg 不在本工程授权范围，本次未构建、修改上游或更改真实 VidAll_TV 架构声明。
