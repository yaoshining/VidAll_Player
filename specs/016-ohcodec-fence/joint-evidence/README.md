# 当前 SDK 联合验收记录

2026-11-11。此目录只记录本轮实际观察；不是对 API 19 TV 真机的替代验收。

## 产物与测试边界

- Player 提交 d287e457445056f30a382e5332730446d78a7bbc；[iMac 自托管 CI 42914926664](https://github.com/yaoshining/VidAll_Player/actions/runs/42914926664) 构建合并预览 af91823a4ce97d4bb52e4332a4b4ed6be291dc32。HAR 和九库哈希见 `ci-binding.json`。12 项检查通过。
- HAP 是本地签名的诊断消费包，基于上述 CI HAR；不是最终 CI HAP。正常包九库逐字节匹配 HAR。Vulkan 包仅替换 libmpv，Stop/Destroy 包仅替换上游已交付的对应 libavcodec。
- 消费端临时副本基于 VidAll_TV 96a6baa1a821dbf8f77445ffc7f4bc9d23110360，使用实际 PlayerPage、VideoPlayerController、MpvAudioFocus 和 MPV 适配器；增加离线素材、测试按钮、进度/参数记录和设备输出幅度采样。测试列表不等于正式文件浏览入口验收。没有修改真实 VidAll_TV 工作区。
- A/B 是自制 H.264/AAC 测试片；坏片是缺失 moov 的 MP4。截图为云设备真实视频流回读。声音证据是设备输出幅度与播放时间配对，不是浏览器扬声器人工听辨。
- Vulkan 诊断使用 `native/tests/ohcodec-fence/inject-wait.patch` 和本目录 `surface-diagnostic.patch`，替换库 SHA-256 af8e996e16804c159e6a919fe8fc823aafdefa17c19a233cb74e33d36f98ed35。正常生产 mpv 不含这些注入。

## API 24 云平板

正常包在 MatePad Air 的 PID 5375 中观察坏片失败页返回，随后 B/A 出现变化画面，日志有 OHCodec、NV12、Vulkan 与非零音频输出。坏片失败瞬间未留存 PID 日志，不能把此项描述为完整的坏片同 PID 链路。见 `cloud-normal-fence.txt`。

Vulkan 包在 MatePad Mini（MLR-AL10，设备信息显示 6.1.0.125(SP20C00E125R1P4)，目录标签为 6.1.0.135）完成如下连续操作，PID 均为 23505。见 `cloud-vulkan.log` 及配对图片。

| 操作 | 观察与范围 |
| --- | --- |
| A 硬解关闭 | 07:08:45 在真实等待成功后注入 -4；约 5 秒前台超时，07:08:51 列表仍响应。初始设备静音，A 音频幅度为零，不计为 A 声音通过。 |
| 故障后 B | 调整媒体音量后，07:13:17 新 Surface 100953206292481；NV12/Vulkan，媒体时间推进，输出幅度非零，`vulkan-b-1/2.jpg` 画面变化。 |
| 延迟关闭 | 07:13:23 开始 7 秒延迟，07:13:28 前台超时，07:13:30 后台完成且列表可用。 |
| 名额回收 | 随后实际点击的是“中断后退出并重播”，不是普通 B 按钮。07:14:20 新硬解 Surface 100953206292482，播放和恢复阶段音频正常，证明上个延迟会话的名额可再使用。 |
| 第二次关闭错误 | 07:14:28 注入 -4；同 PID 自动重开 A 时因两个名额占用转软件解码，媒体时间和声音恢复。 |
| 上限后手动 B | 07:15:07 再开 B，明确记录 software decode / hwdec-current:no / yuv420p。`vulkanSoftFrame1/2.jpg` 显示不同帧，输出幅度非零；`vulkan-list-final.jpg` 是最终列表。 |
| 再次坏片返回 | `vulkanBad.jpg` 是实际失败页；返回后 `vulkanAfterBad.jpg` 是 B 画面，`cloud-vulkan-after-bad.log` 保留同一 PID 23505 的后续播放、非零音频及列表返回。坏片自身 PID 仍未直接落入保留日志。 |

首次 A 的 decoder Surface ID 被云日志滚动淘汰，不能用输出窗口 ID 代替。已记录的 B/第三会话 Surface 不同，证明新会话创建及名额回收，首次故障旧 Surface 与 B 的严格身份对照在下述补测中完成。没有观察到本轮故障使应用退出；这不证明所有 GPU 故障或永久驱动挂起均可恢复。

## API 19 / API 20 模拟器音频

`audio-summary.json` 由同目录原始阶段日志计算，每阶段 32 个设备幅度样本。API 19 TV PID 10538 与 API 20 平板 PID 3345 均覆盖：正常播放有进度/音频、用户暂停静音、恢复播放、系统中断保持暂停、解除中断不自动续播、一次播放恢复、退出后重开正常片。模拟器使用软件解码；不计为 TV 真机硬解验收。

换集回归通过临时测试钩子调用真实 `handleEpisodeSelect`。API 19 PID 1614 通过；API 20 PID 6734 换到 index=1 后 `playing=false`、进度 0→0、幅度全零，因此 R8/T021 仍失败。API 20 仅在钩子中先调用现有 `allowPlaybackFromUser()` 的对照包 PID 13796 恢复播放、进度 0→1500 与非零音频。两包九个 Player 原生库完全一致。

定位：API 20 的 MpvAudioFocus 将控制器 `playbackBlockedUntilUserAction` 置为 true，选集路径没有清除此状态，新媒体的播放事件又被控制器暂停。建议 VidAll_TV 在明确的用户选集入口恢复播放意图，并添加“中断→用户选集→新媒体音画”和“中断结束不自动续播”的回归。对照钩子不是正式修复；本项目未修改真实消费端，不能把 API 20 换集计为通过。

## 上游 Stop / Destroy 联合验证

两轮都在上述 MatePad Mini 上完成，见 `cloud-stop.log`、`cloud-destroy.log` 和配对图片。消费上游既有探针，未修改、编译或发布 FFmpeg。注入是首次已启动 decoder 的一次关闭调用跳过平台调用并返回 6；后续调用为真实平台调用。

- Stop：PID 55925，07:30:32 `stop skipped=1 rc=6`，随后真实 Destroy=0；07:30:39 列表。B 的 decoder 2 使用 Surface 240196046028801，区别于旧 Surface 240196046028800；OHCodec/NV12/Vulkan、变化画面、非零音频及最终正常关闭/列表均已记录。
- Destroy：PID 59038，07:32:12 真实 Stop=0，`destroy skipped=1 rc=6`；07:32:18 列表。B 使用 Surface 253566279221249，旧 Surface 为 253566279221248；同 PID 硬解音画正常，B 的真实 Stop/Destroy 均为 0，07:32:47 回到列表。
- Stop 的 `P27_VK acquire/hold/release` 摘录保留缓冲区序号、fence、返回码；Destroy 摘录保留 owner-init/acquire，未留存其逐帧 release 行。原始地址已替换。该观察证明实际使用原生缓冲映射，Stop 记录还直接证明逐帧归还；不推断未注入的驱动永久阻塞行为。

### 小包复现边界

T3 上传上限为 50 MiB。外层压缩 APP 尝试被云端签名检查拒绝，未计为验收。最终小 HAP 使用 release 编译、原生库压缩最高档，并在临时 fixture 的 PackageHap 前将 `app.debug=true` 以保留设备阶段日志；签名仍由本地 DevEco 完成。仅 B 截到 22 秒、损坏文件截到 4096 字节，A 和播放逻辑未改。每个验收包重新检查九库身份、占位配置和无私密配置泄露。普通 release 包只观察到画面/列表但缺少 INFO 阶段日志，不计为注入通过。`hap-binding.json` 中 `*-compact` 对应最终可观测包。

## Vulkan Surface 身份补测

小包 PID 61877：07:33:52 A 的 Surface 为 265759691374592，真实 OHCodec/NV12/Vulkan；07:33:58 关闭等待注入 -4，07:34:03 前台超时，07:34:05 返回列表。07:34:24 B 取得新 Surface 265759691374593，未复用被隔离的旧 Surface。`vk2BFrame1/2.jpg` 为变化画面，对应非零音频与推进的播放时间；日志与原生缓冲映射摘录见 `cloud-vulkan-surfaces.log`。

## 正常九库坏片返回补测

无注入 `normal-compact` 在 PID 65452 中完成：07:35:58 对坏 MP4 记录 `moov atom not found` / `NATIVE_PLAYBACK_FAILED`，失败页点击返回后重新进入列表；07:36:32 B 进入 OHCodec/NV12/Vulkan，有变化画面与非零音频；随后 A 同样正常硬解音画，07:37:10 列表仍可用。见 `cloud-normal-final.log`、`normalBadFrame.jpg`、`normalListAfterBad.jpg`、`normalBFrame1/2.jpg` 与 `normalAFrame1/2.jpg`。该补测完成坏片同 PID 链路；前面的 Air 和 Vulkan 坏片截图仅保留为各自独立记录。

云设备已于 07:37 后通过“直接释放”结束，页面返回机型目录；优惠余额 306 分钟。未开启按量付费。

归档 FenceProbe.ets 仅移除了行尾空白；fixture-binding.json 记录实际构建输入原文的哈希。
