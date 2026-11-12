# T044：云平板关闭恢复复验（2026-11-12）

本轮拿到 API24 MatePad Mini 真机，完成真实 OHCodec/Vulkan 资格确认、mapper 关闭错误注入、返回列表、晚关闭回收、连续隔离上限、全局终局后的兼容续播，以及普通坏片后的重新播放。**仅视频画面、进程、状态和系统音频流证据通过；可听音频、真实系统音频打断和 API19 TV 正式入口仍未验收，不提 PR。**

## 来源和范围

- 设备：MLR-AL10，HarmonyOS 6.1.0.125(SP20C00E125R1P4)，API24，1600×2560。约 12:17–12:50 使用免费云调试，结束后释放设备，余额327分钟，未购买。保留浏览器页及已上传包。
- 源基线：`d4a059b3117a23d70aa0832d00ed7161fd8c6d5a`；本次分支此前文档提交 `96cfef6`。新增 T044 只改 Player NAPI 关闭顺序和回归，未改 FFmpeg、VidAll_TV、解码优先级或 mpv 核心。
- 最终三套 HAR 均由 Player 工程完整构建；实际机器为本地 MacBookPro18,4 / Darwin arm64，**不是最终 CI 交付**。HAP 声明 tv/tablet，九库无损压缩，逐库与各自 HAR 相同。六个 FFmpeg 库沿用固定输入；诊断核心沿用 T042/T043，普通包沿用正式 mpv `ee78bf…5267`。
- 完整 HAR/HAP 和九库哈希分别见 `fence-audio-rebuild.json`、`global-final-package.json`、`normal-final-package.json`。最终源码文件哈希见 `result.json`。ARM64 九库支持边界未变，没有补造 x86_64 支持。
- 为观察播放中的系统音频流，仅在本地验收页面把 fence 的观察等待1500ms、全局恢复 B/C 的700ms延长到8000ms，原资格/状态断言不变；具体 fixture 哈希在清单中。这不是延长原生安全截止时间。
- `*-selected.log` 只保留对应 PID 的 P17/P17F 和 FENCE_PROBE 行；完整原始云日志留在本地 `/tmp/vidall-t044-cloud-tablet`，不提交其他应用日志。`*-events.jsonl` 来自本应用沙箱的持久化记录，按本轮最后一个 runtime 事件截取。

## 真实失败与修复

1. 原 d4a059b 关闭探针在 PID8900 确认硬解，12:22:13 注入 mapper wait `-4`。5秒释放超时后 UI 仍走，但关闭 owner 故障没有到达独立订阅，12:22:28 报 `INDEPENDENT_CLOSE_FAULT_TIMEOUT`。原因是 GPU-next VO 在 `mpv_terminate_destroy` 内才清理，而客户端与事件观察线程先被关闭。该失败保留在 `fence-repro-hilog-selected.log`。
2. 先添加提取真实 `NativeSession::Release` 的失败回归，再在事件观察者仍存活时正常配置 `vo=null`，之后才关闭 renderer/事件线程/句柄。此版四会话流程走完，但系统 dump 显示已隔离 A/C 的音频流100082/100084仍为 RUNNING（PID24530，`fence-audio-running.txt`），不能作为通过结果。
3. 再补音频关闭顺序红测，修正为 **`ao=null` → `vo=null` → 原有安全关闭**。只影响 Vulkan 会话释放，不改变正在播放的零拷贝硬解。重配置在既有有界实例执行器内执行；超时仍保留调用栈、surface、对象和预算；返回错误则隔离并发布不可归属故障，不先销毁未知资源、不提前归还槽位。
4. 新回归覆盖正常释放、晚成功、晚 owner 故障、AO/VO 拒绝关闭、未初始化、软件路径及幂等释放；原有父链替身同步字段/API。红绿日志在本目录。最终统一宿主门禁94/94通过（`host-gate-summary.json`），另有回调清理和初始化回归通过。本地完整普通/两组诊断 HAR/HAP 编译通过。

## 最终实机结果

| 流程 | 证据 | 结果与边界 |
| --- | --- | --- |
| A 关闭隔离 | PID35486；actual vulkan/ohcodec；owner session1/load1；release91ms | 独立隔离故障可达；点击返回列表。释放后系统音频流0。完整页面持久化事件保留；A 原生早段当时已观察，但因云端滚动日志窗口未完整导出，不能声称原始日志完整。 |
| B 晚关闭 | 同 PID；actual vulkan/ohcodec；12:39:49→12:39:56 `late-close-end real=0` | 接口约5004ms返回，UI继续25次心跳；原生实际关闭后再手动确认。播放中只有本实例音频流100087 RUNNING。 |
| C 新硬解及第二次隔离 | 同 PID；actual vulkan/ohcodec；owner session3/load1；release55ms | B 真正关闭后硬解槽可复用；第二次 `-4` 注入独立归属正确。返回列表后系统音频流0。 |
| D 达隔离上限 | 同 PID；actual vulkan/no；四会话均出现首帧 | 达到两次隔离上限后软解，Vulkan仍作渲染；仅新流100089 RUNNING，释放195ms后音频流0。runtime仍ready。 |
| 全局终局兼容续播 | PID47972；原会话 actual vulkan/ohcodec；timer-global注入 | 原生终局仍锁存，recovery.ready generation2；新Surface上的B/C均首帧，B actual software/no、进度9133ms、AAC轨。三次首帧、恢复后错误0。旧流100090停止，C流100092运行；结束后仅保留停止的100090。 |
| 普通最终修复包 | PID51050；无注入正式mpv核心 | 坏MP4失败→正常硬解；暂停前后833ms稳定，恢复到1566ms；seek20秒后继续；释放再开共2首帧、后续错误0；结束音频流0。 |
| 原始 iMac CI 包对照 | PID16385；HAR `a8ce9ee5…ab3da1d3` | 同日先独立验证坏片返回、硬解首帧、暂停恢复、seek和释放重开通过。此旧包不含T044，不能替代最终修复包。 |

全局隔离会话保留 STOPPED/PAUSED 的音频对象，是有界退休资源的一部分，**不是全部对象已经释放**。新会话的运行流独占与旧流停止已由系统 dump 观察；不能从流状态推断扬声器实际出声。全局定时注入只证明恢复链条，不证明自然 GPU 全局故障的全部触发路径。

最终画面见 `fence-final-{b-playing,d-playing,summary}.png`、`global-final-{c-playing,screen}.png`、`normal-final-screen.png`。以服务器截屏取证，云浏览器 video 元素画面曾停滞，不能依赖其旧帧判断当前画面。截图是诊断页面，不是 TV 正式文件入口。

## 仍开放的验收

- 云调试 `playerVideo.captureStream().getTracks()` 实测只有一条 live video，没有 audio。没有可靠听声/PCM录音证据；Speaker 路由、AAC轨和 RUNNING 状态不等于“有声音”。本轮不标记 audibleAudioAccepted。
- 本轮 pause/resume 是显式播放器操作，未触发另一个真实系统音频焦点持有者，不能冒充音频中断及中断解除后的手动恢复验收。
- 平台 Stop 永久不返回/静止未知、builder特定错误等仍保留现有边界；本轮没有注入这些平台错误，也没有强行放行。
- 还需新修复源的 iMac CI 完整 HAR、其设备复验与 API19 TV 正式文件入口。设备遥控器交互、TV消费状态问题#371和媒体标记#372仍由消费端分别跟踪。

## Spec Kit 一致性

S18/S18a → plan T044 → Release 实现 → release-owner-lifetime.test.py → 94项宿主门禁 → 本目录三类本地包与分层设备记录。宪章第四/六条：关闭位于实例执行器、保留未知资源与固定预算；第五条：只提交脱敏自身应用日志与测试素材截图；第八/十条：先红后绿，未删断言、未用本地构建或API24结果冒充CI/TV/声音验收。T044修复切片完成；T007/T009/T013/T017/T018的剩余验收继续开放。
