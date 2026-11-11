# 全局终局同进程恢复诊断探针

仅与 Player 工程构建的独立诊断 HAR 配合使用；不得作为正式交付。将 `native/tests/host-survival/inject-process-terminal.patch` 应用于已锁定 mpv 输入，重新生成输入清单，使用 `--handoff-trace --handoff-test` 构建。它在首次加载文件名含 global-probe.mp4 的媒体后 3 秒调用真实终局管理器，退休旧代并锁存终局；**没有制造真实 GPU/fence 故障**。诊断库及 HAR/HAP 哈希必须与正常 CI HAR 分开记录。

页面默认 `hardware-first`：首片以 `standard` 打开，首帧后必须从有效、非估算的实时诊断确认 `renderBackend=vulkan`、`hardwareDecoder=ohcodec`，否则报告 `HARDWARE_PATH_REQUIRED` 并停止验收。模拟器只允许显式改用 `software-control` 对照配置，首片和后续均为 `compatible`，不得据此声称硬件路径通过。随后等 terminal 与 recovery.ready，核对已登记身份对应故障记录、旧会话命令拒绝，再用全新 XComponent/Surface 播放另一部素材。恢复后的第二、第三会话必须实际报告 `software/no`。旧 Surface 保留在原组件，避免复用仍被旧实例持有的窗口。再次释放后，为第三个兼容会话创建独立 XComponent/Surface，仍保留前两个组件，确认终局锁不复位。release 接口完成不是允许复用旧窗口的证明。旧实例 release 按当前合同返回 PLAYER_TERMINAL，页面不能把该拒绝当作“必须退出应用”；新兼容实例即使全局仍 terminal 也必须正常释放。离页取消未完成流程，旧监听器迟到的首帧或状态不能满足新实例的等待。

将本目录的 `Index.ets`、`ProbeChecks.ets`、`ProbeProfile.ets` 一并复制到独立消费工程的 `entry/src/main/ets/pages/`。默认保留 `ProbeProfile.ets` 中的 `hardware-first`；模拟器对照仅在独立工程将其改成 `software-control`，记录配置文件哈希、HAR/HAP 哈希、PID 和日志。`summary` 包含 profile 与 `scope=timer-global`，硬件条件不满足时不得出现成功总结。

此定时探针的身份直接来自 load 命令，只证明相应登记身份的终局传递，不能证明 decoder → mp_image → last_src 的帧归属；后者使用相邻 `recovery-fence/` 的真实 mapper 关闭接缝。两类证据分别保留，不能关闭生产 owner 隔离来合并制造“全局故障”。

需两个 rawfile：global-probe.mp4 为 30 秒 SMPTE 色条/880 Hz 合成素材；test_video.mp4 使用相邻 recovery/README.md 的移动图案/440 Hz 素材。两者都以每秒关键帧编码。测试音频状态/进度不代替可听音频或真实系统打断验收。

T034 已修复旧验证器额外要求已移除 waiting 导出的问题。正式/诊断核心共用精确的 64 公开符号契约，诊断额外验证内部注入及真实终局调用；T035 独立诊断核心完整构建与静态检查通过。该结果不改变诊断包的非正式交付属性，也不证明真实 GPU/fence 故障或可听音频。

诊断 Player HAR 必须使用 `devecocli build --product default --modules vidall_player@deveco26`，从 `packages/vidall-player/build/default/outputs/deveco26/vidall_player.har` 取包。`default` 模块目标还会携带两个 x86_64 探针库；它们不提供播放能力，不能据此扩大支持架构。验证消费 HAP 时同时记录全部库与实际设备 ABI，正常 CI 候选必须为 ARM64 九库。
