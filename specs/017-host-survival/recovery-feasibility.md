# 全局故障后续播的可行性核对

2026-11-11，用户明确拒绝“本次运行禁用 MPV，重启后恢复”。本记录是源码及官方能力调查，不是已实现或设备通过。

## 修正此前过宽的结论

OHCodec 全局状态不能安全复位，并不等于所有软件播放路径都无法工作。实际生产编译树中，terminal_can_start/begin_creation/end_creation 的使用局限于 OHCodec interop；没有发现 mpv_create/mpv_initialize 或软件渲染器直接依据该锁拒绝新实例。目前禁止所有新播放的是 Player 的 AdmissionError、ArkTS assertPlayerRuntimeReady/playerTerminalError 及各入口的 state==4 检查。

因此“保留硬解全局禁令，新建完全不进入该故障域的软件会话”值得验证。它不是复位旧实例，不清除 admission CLOSED；也不能只删桥接检查。新旧代必须分开准入、事件、清理及资源预算，旧对象继续禁止不安全析构。

已有两名额耗尽的设备验证为 yuv420p + Vulkan，不能证明此处需要的纯软件渲染恢复。现有 SwRenderLoop 具备 CPU RGBA 输出与 PixelMap 后备，但仍需要审查 NativeWindow 请求/fence 等待和旧音频状态，不能称其天然安全。

## 官方设备限制

2026-11-11 查阅 [native_child_process.h](https://developer.huawei.com/consumer/cn/doc/doccenter-references/api/capi-native-child-process-h/)：OH_Ability_StartNativeChildProcess 从 API 14 起支持 PC/2-in-1、Tablet，其他设备类型返回 NCP_ERR_MULTI_PROCESS_DISABLED；[childProcessManager](https://developer.huawei.com/consumer/en/doc/harmonyos-references/js-apis-app-ability-childprocessmanager/) 的 ArkTS/Native 子进程接口同样限制设备类型，其他设备返回 801。因此不能用这条公开 API 给 API 19 TV 承诺进程隔离。此处是官方限制核对，未重做真机调用实验。

[AVPlayer](https://developer.huawei.com/consumer/cn/doc/doccenter-references/api/arkts-apis-media-avplayer/) 提供独立的系统播放接口，但它仍依赖平台媒体服务；不能保证和 GPU/驱动故障完全独立。其格式、轨道、字幕、媒体源及音频行为也不能直接视作与 MPV 等价。

## 先验通过条件

1. 正常仍使用 OHCodec/Vulkan；全局终局后保持硬解禁令，旧资源不析构。
2. 新代强制软件解码和软件渲染，不进入 Vulkan/EGL，不复用旧 Surface、音频控制与回调代。
3. 旧代音频可靠停止，不能把新旧混音的非零幅度算作恢复声音。
4. 有界控制旧线程和保留资源，新代正常关闭后归还资源，重复坏片不继续占用新槽。
5. 全局注入前后同 PID、列表响应、B 的独立运动画面和音频、B/C 连续重播均有证据。真实永久驱动挂起、进程内存破坏不能由返回码注入实验代证。
6. API 19 TV 与 API 24 分别记录；不改变 #83/#84/#89，不以修改消费端 #371 达成 Player 测试。

只有这些门槛通过后，才能把软件恢复作为正式接入契约。本段记录的是实现前调查状态；后续已有 CI 候选 HAR 与软件模拟器结果，见[最新交付](latest-delivery.md)。真实硬件与可听音频验收仍未完成，不能由候选产物或模拟器结果代替。

用户后续明确：接受全局终局后本次运行暂用兼容路径，但不接受跨重启让所有视频持续降级。重启后仅对实际发生故障的问题视频保留兼容选择，其他视频仍优先硬解。这不会使已锁存的旧进程重新开放硬解，也不能据此宣称兼容路径已验证。普通坏片和可隔离会话故障仍应局部处理，不主动升级成全局故障。
