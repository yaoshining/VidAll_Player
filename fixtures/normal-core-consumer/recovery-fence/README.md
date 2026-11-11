# 真实 close/wait 的会话隔离与名额回收诊断

本目录对应 Spec 017 T037，只准备设备验收流程。宿主回归通过不代表 OHCodec/Vulkan、API 19 TV、同进程画面或可听音频已验收。页面只使用 `standard`，第一部素材必须报告实际 `renderBackend=vulkan`、`hwdec-current=ohcodec`；模拟器软件路径、`ohcodec-copy`、估算字段或终局缓存快照都不能通过硬件门槛。

## 诊断包与准备

1. 在 Player 工程的独立诊断输入副本中，仅应用 `native/tests/ohcodec-fence/inject-wait.patch`，重新生成对应输入清单并构建完整诊断 HAR。不要同时应用 `inject-process-terminal.patch`，不要关闭 owner 隔离，也不要更换、修改或构建 FFmpeg。补丁只在真实 Vulkan close/wait 已返回 0 后注入结果；没有真实关闭路径就不会触发。
2. 新建或使用独立消费工程，完整接入该诊断 HAR。将本目录的 `Index.ets`、`FenceRun.ets` 和相邻 `../recovery-terminal/ProbeChecks.ets` 一并复制到消费工程 `entry/src/main/ets/pages/`；`ProbeChecks.ets` 是共享门槛源码，不要以另一份宽松实现代替。T037 不使用 `ProbeProfile.ets`。
3. 提供两个 rawfile：`global-probe.mp4` 是 30 秒 SMPTE 色条、880 Hz 音频；`test_video.mp4` 是相邻 `../recovery/README.md` 的移动图案、440 Hz 音频，均每秒一个关键帧。这里的 `global-probe.mp4` 只是不同素材的文件名，不能带入全局定时故障补丁。
4. 先记录源提交、补丁哈希、真实构建机器类型、原始 HAR/HAP 哈希、九库哈希、设备型号、API、ABI、两个素材哈希。每轮从全新进程开始；保留该 PID 的原始 hilog 和画面/音频证据。页面日志前缀为 `P17F`，沙盒记录在 `files/phase17-fence/events.jsonl`。

诊断 HAR 不得替代最终 GitHub Actions CI 交付，也不得在 VidAll_TV 中解包修改 Player。生产产物与诊断产物的清单及验收结论必须分开记录。

### 当前可复现构建约束

以已锁定 T035 输入的独立副本为基线（package SHA-256 `60e24caba7b2bbd5cfc72dd572fcd5f5c747ac09343d6e75bf345e3a6413a650`），不要对已打生产补丁的输入再次运行基线准备器。应用 `inject-wait.patch` 后，在临时 `sources/mpv/meson.build` 的 OHOS 音频依赖列表额外链接 `cc.find_library('hilog_ndk.z')`；清单仅重锁该文件和 `video/out/hwdec/hwdec_ohcodec_pl.c`，注明 `formalArtifactAllowed=false`、诊断补丁哈希与未改 FFmpeg。

使用 `native/tooling/normal-core/fresh_build.py` 的全新 `--run-root` 和已有预编译 SDK，保留 `--handoff-trace`。**不加 `--handoff-test`**（它要求另一套 global probe），**不加 `--ohcodec-diagnostic`**（本补丁位于该宏的 else 分支），不启用 experiment/return-replacement。完成后检查精确 64 公开接口、库中三个 `FENCE_PROBE` 标记以及 global probe 不存在。

在 Player 临时诊断工程接入此核心并执行 `devecocli build --product default --modules vidall_player@deveco26`，获取完整 ARM64 九库 HAR，再完整接入消费者。实际清单、核心/包哈希、构建机与模拟器资格负例见 `specs/017-host-survival/device-evidence/api19-t037-fence-negative.json`；正常 CI 来源锁及 HAR 不得替换。

## 页面流程与真实故障合同

| 步骤 | 真实关闭注入与页面操作 | 必须核对的结果 |
| --- | --- | --- |
| A | 新 Surface、新实例用 `standard` 播放色条素材；第一次真实 close/wait 将成功返回值改为 `-4` | A 确实 OHCodec/Vulkan、有首帧和进度；独立 `onPlayerFault` 收到 A 的 `session-quarantined`、`stage=1`、`platformError=-4`，session/load 与 A 的不可变回执一致；runtime 仍 `ready` |
| 返回与 B | 点击“返回视频列表”，再点击“播放另一部视频”，用新 Surface/实例播放移动图案 | 旧 A Surface 保留；B 的回执、Surface 均不同，仍实际 OHCodec/Vulkan；有画面、进度，另行核对可听音频 |
| B 晚关闭 | 第二次真实 close/wait 在底层成功后延迟 7 秒再返回；释放接口约 5 秒结束 | 关闭中页面 UI 心跳持续；原始日志必须出现本轮同一 PID 的 `FENCE_PROBE late-close completed real=0`；不能出现 B 的隔离故障 |
| C | 操作者核对上述原生日志后点击确认按钮，才允许新 Surface/实例播放色条；第三次真实 close/wait 再注入 `-4` | C 必须再次实际 OHCodec/Vulkan，才能证明晚关闭归还了硬解名额；按钮本身不算证明。C 隔离故障的 session/load 必须指向 C，不能误记为 A 或 B |
| 返回与 D | 再点击返回列表和播放另一部，D 仍请求 `standard` | A、C 已占满两处硬解隔离名额，D 必须实际 `hwdec=no` 且首帧/进度正常；记录实际 renderer。这里可能继续用 Vulkan 渲染软件解码帧，并非强制 `compatible` 软件渲染 |
| 结束 | D 释放完成、常亮关闭，再输出页面 `summary` | 全程同一主进程 PID，无主应用退出、无全局 terminal；只有 A、C 两条归属正确的隔离记录。`summary` 明确保留原生日志和可听音频证据待审阅状态 |

**`release()` 成功只表示接口调用结束，不能证明原生资源已经安全销毁。** 当前 `QueueNative` 会将 retire 路径上的 `SESSION_QUARANTINED`、`NATIVE_WORK_TIMEOUT` 归一为 `RELEASED`。本页因此在 release 期间及之后持续订阅独立运行时故障，不通过 release 拒绝来识别隔离，也不会把 Promise 完成当成安全释放的证据。

A、C 的不安全资源继续由原有有界隔离保留；页面保留旧 XComponent，后续实例都取得新 Surface。B 的迟到关闭是否结束由原始设备日志确认，之后 C 的实际硬解诊断再次验证名额回收。D 软件回退用于验证隔离上限，不复位全局故障、不释放安全性未确认的资源、不修改正常零拷贝路径。

人工确认最多等待 120 秒，页面退出可取消。各阶段按钮具有 TV 默认焦点；故障后的返回键也可进入诊断列表。确认只能在等待阶段生效；它没有读取日志的权限，只负责推进测试，审阅人仍须核对原始 hilog 的 PID、时间顺序和该轮包哈希。点击确认后 C 若只走软件，流程仍失败。日志缺失、未知身份、错误故障码、多余故障、旧 Surface/实例复用或任何 terminal 都必须判失败。

## 分层证据与当前边界

宿主测试执行实际 `FenceRun.ets` 及页面方法；解码器、平台 NAPI、ArkUI 声明式渲染和人工确认是替身：

```sh
node native/tests/host-survival/recovery-fence.test.cjs
node native/tests/host-survival/recovery-fence-page.test.cjs
```

两项回归覆盖关闭后独立故障投递、身份/故障码校验、重复历史、额外故障、原生日志确认门槛、C 名额未回收、D 未软件回退、runtime terminal 拒绝、真实页面的 `standard` 绑定和 UI 心跳、返回键、页面离开后的初始化取消，以及清理失败不生成成功总结。门槛失败前的 `playback-observed` 只记录实际诊断，不代表通过；例如模拟器 `software/no` 必须保留为资格负例。页面方法测试会移除 ArkUI 的声明式 `build` 后执行，不代表 ArkTS 目标编译或真实 UI 行为。

此准备项不声称已执行目标设备。最终证据需分别记录宿主、目标构建、模拟器软件负例、OHCodec/Vulkan 真机四层。API 24 平板结果不能替代 API 19 TV 验收；音频 codec 和播放进度也不能替代可听音频。人工返回的是本诊断页的列表，仍需 VidAll_TV 从正式文件入口完成宿主回归。正常播放、系统音频打断及手动恢复、切集等 T029 场景仍独立验收，不将消费端 #371 的暂停标记问题计入 Player 修复。
