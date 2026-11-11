# 2ad7fdd 新桥接库云平板复验

2026-11-11 08:14–08:25（北京时间）。T025 的新桥接库设备复验通过；本目录不替代 API 19 TV 真机验收。使用华为云调试交互操作真实平板，未运行云测试自动任务。

## 输入与方法

- Player 源提交 `2ad7fdd3a8182bbb009319c8bdbef8ba846e4818`；[iMac 自托管 CI 42927679634](https://github.com/yaoshining/VidAll_Player/actions/runs/42927679634) 构建合并预览 `c034b98b55b2103a9aa2811095f539ffc44ee3f7`。HAR SHA-256 `8cc1e1c9d34c2f79a091d67ce210bb557dd530505670bb40d64c42cca9a6c49e`；桥接库 SHA-256 `96d62ea499a18d66e951873b85e505ff091ccbe33d42cc019949b65ae56c0dd3`。九库绑定见 [ci-binding.json](ci-binding.json)。这不是云端 Mac 构建。
- 设备 MatePad Mini MLR-AL10，API 24，系统信息 `6.1.0.125(SP20C00E125R1P4)`。本轮结束后直接释放设备，页面确认解除占用，优惠余额 294 分钟；未开启按量付费。
- 四个 HAP 是本地签名的诊断消费者，基于该 CI HAR。正常包九库完全一致；Vulkan 包只替换已有诊断 mpv；Stop/Destroy 包只替换上游已交付的对应探针 libavcodec，未修改或构建 FFmpeg。全部包使用相同的新 NAPI 桥。完整 HAP、九库哈希、大小和替换项见 [hap-binding.json](hap-binding.json)。
- 临时 VidAll_TV 消费副本基于 `96a6baa1a821dbf8f77445ffc7f4bc9d23110360`，沿用实际 PlayerPage、控制器及 MPV 适配器；离线列表、自制 A/B/坏 MP4 和小包策略承接 [联合夹具](../joint-evidence/README.md)。实际新夹具源码及输入哈希在本目录，音频采样沿用 [FenceAudioProbe.ets](../joint-evidence/FenceAudioProbe.ets)。真实 VidAll_TV 工作区未修改。
- 配对 JPG 是云设备视频流的真实帧回读，片内时间码及图案变化用来确认画面；声音以设备输出幅度和媒体时间配对确认，未声称浏览器扬声器人工听辨。每阶段 32 个样本，摘要见 [audio-summary.json](audio-summary.json)。日志仅截取相关阶段，去重、补齐相邻快照间的换行并将原始地址脱敏，不是完整系统崩溃日志。

新增 Worker 用例的复放配置：将 `CleanupProbe.ets` 放入临时消费者的 `entry/src/main/ets/pages`，`CleanupWorker.ets` 放入 `entry/src/main/ets/workers`；entry 的 `build-profile.json5` 中 `buildOption.sourceOption.workers` 登记 `./src/main/ets/workers/CleanupWorker.ets`，entry 模块直接引用 HAR 提供的 `libvidall_player_native.so` 类型定义。`FenceProbe` 注册对应 NavDestination。四包使用相同夹具，生成包中的 `app.debug=true` 仅为保留阶段日志；正常九库内容不变。绑定文件记录实际编译前原文（归档仅去除行尾空白）及三份素材的哈希。

## 实际结果

| 场景 | 同进程证据与结果 |
| --- | --- |
| 普通坏片返回 | PID `13834`，08:14:05 `moov atom not found` / `NATIVE_PLAYBACK_FAILED`；失败页手动返回列表。随后 B 正常播放；08:15:05–12 再次记录 OHCodec/NV12/Vulkan、推进的时间和非零音频。见 `normal.log`、`normal-bad.jpg`、`normal-list.jpg`、`normal-bframes-1/2.jpg`。 |
| 非隔离环境清理 | 同 PID `13834`，08:15:37 Worker 创建 `hwdec=no` 会话并实际输出软件解码画面与音频。08:15:50 直接 terminate Worker，未调用 releaseSession；退出回调 code=0，13 ms，主 UI 心跳从 126 继续到 230。08:16:17–23 返回列表后 B 硬解音画正常，08:16:30 列表可用。见 `cleanup.log`、`normal.log`、`cleanup-frames-1/2.jpg`、`cleanup-terminated.jpg`、`cleanup-alive.jpg`、`cleanup-bframes-1/2.jpg`。 |
| Vulkan 关闭错误 | PID `20464`，08:17:41 A 真实等待成功后注入 -4；08:17:47 列表可用。A 的原生缓冲 consumer=`87892210745344`，08:18:11 B 新 consumer=`87892210745345`，硬解音画正常。见 `vulkan.log`、`vulkan-list-a-frame.jpg`、`vulkan-bframes-first/second.jpg`。 |
| 延迟关闭回收 | 同 PID `20464`，B 于 08:18:17 开始 7 秒延迟；08:18:23 列表已响应，08:18:24 后台完成。08:18:44 再开 A，consumer=`87892210745346`，仍为硬解且有音画，证明延迟成功后名额可再次使用。见 `vulkan-cframes-first/second.jpg`。 |
| 隔离上限降级 | 同 PID `20464`，08:18:50 第三会话关闭再次注入 -4；两个名额被保留。08:20:57 再开 B 明确记录 `OHCodec session limit: software decode`、yuv420p/Vulkan；时间推进到 4583 ms、音频非零、画面变化，08:21:09 列表可用。见 `vulkan-dframes-first/second.jpg`、`vulkan-list-d-frame.jpg`。 |
| FFmpeg Stop 错误 | PID `27417`，08:22:23 首次关闭 `stop skipped=1 rc=6`，真实 Destroy=0；08:22:30 列表响应。B 使用新 Surface `117755118354433`（旧为 `117755118354432`），硬解音画正常，08:22:47 真实 Stop/Destroy 均为 0，08:22:53 列表可用。见 `stop.log`、`stop-bframes-first/second.jpg`、`stop-list-b-frame.jpg`。 |
| FFmpeg Destroy 错误 | PID `30199`，08:23:57 真实 Stop=0，`destroy skipped=1 rc=6`；08:24:03 列表响应。B 使用新 Surface `129703717371905`（旧为 `129703717371904`），硬解音画正常，08:24:22 真实 Stop/Destroy 均为 0，08:24:28 列表可用。见 `destroy.log`、`destroy-bframes-first/second.jpg`、`destroy-list-b-frame.jpg`。 |

上述各场景内故障前后 PID 连续，均未观察到故障导致整个应用退出；不同包安装后 PID 改变是独立实验。Stop/Destroy 日志还保留实际 hold、fence、release-begin/release-end rc=0 的逐帧归还片段；不是仅依据选项 auto 推断零拷贝。

## 清理验证与剩余边界

Worker 是同一应用进程内的独立 NAPI 环境，实际动态库、事件回调、Surface、解码和渲染均在运行。测试在活动播放期间触发环境退出，证明本设备的环境清理能及时返回、主 UI 存活且后续新会话可用。13 ms 是调用 terminate 至退出回调的单次观测值，不是通用性能保证。未在真机强制制造永久阻塞析构，也未确定性控制排队 TSFN 的竞态；这两类由 T024 的真实生产函数宿主回归验证，不能把本实验夸大为所有 GPU 挂死均可恢复。

Vulkan 注入修改的是真实等待成功后的返回值；上游 Stop/Destroy 探针跳过首次调用并返回 6。它们验证隔离和恢复合同，不证明真实驱动永久挂起、反复 Destroy 失败的长期耗尽或 4K/HDR 性能。

API 19 TV 真机和正式文件浏览入口仍未验收；云调试当前目录无 TV，云平板不能替代该驱动层覆盖。API 20 中断后用户选集状态问题仍按 [VidAll_TV #371](https://github.com/yaoshining/vidall-tv/issues/371) 跟进，R8/T021 保持未完成，自动连播不得借用户意图清理绕过暂停。此项不通过不归因于零拷贝解码。

本轮只新增诊断夹具与证据，未修改生产代码。Spec Kit 前置检查通过；宪章核对 R7/R9/R10 → T025 → 当前 CI 桥接库 → 上述设备记录，历史 d287e45 证据未混入本轮。生产代码 49 项宿主及其余既有回归以 2ad7fdd 的本地红绿记录和本次 CI 为准。
