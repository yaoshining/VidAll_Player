# 全局终局同进程恢复诊断探针

仅与 Player 工程构建的独立诊断 HAR 配合使用；不得作为正式交付。将 `native/tests/host-survival/inject-process-terminal.patch` 应用于已锁定 mpv 输入，重新生成输入清单，使用 `--handoff-trace --handoff-test` 构建。它在首次加载文件名含 global-probe.mp4 的媒体后 3 秒调用真实终局管理器，退休旧代、锁存终局并保留注入线程；**没有制造真实 GPU/fence 故障**。诊断库及 HAR/HAP 哈希必须与正常 CI HAR 分开记录。

页面先用 compatible 播放第一部素材，等 terminal 与 recovery.ready，核对已登记身份对应故障记录、旧会话命令拒绝，再用全新 XComponent/Surface 播放另一部素材。旧 Surface 保留在原组件，避免复用仍被旧实例持有的窗口。再次释放、重建新兼容会话，确认终局锁不复位。旧实例 release 按当前合同返回 PLAYER_TERMINAL，页面不能把该拒绝当作“必须退出应用”。

需两个 rawfile：global-probe.mp4 为 30 秒 SMPTE 色条/880 Hz 合成素材；test_video.mp4 使用相邻 recovery/README.md 的移动图案/440 Hz 素材。两者都以每秒关键帧编码。测试音频状态/进度不代替可听音频或真实系统打断验收。

当前导入静态验证器的历史 test 模式还期望已移除的 mpv_ohcodec_handoff_test_waiting 导出，因此该诊断构建在完整编译链接后未通过该旧测试导出断言。正常核心 64 导出门禁通过；不为此放宽正式门禁，也不把诊断包称为已通过正式输入审计的产物。

诊断 Player HAR 必须使用 `devecocli build --product default --modules vidall_player@deveco26`，从 `packages/vidall-player/build/default/outputs/deveco26/vidall_player.har` 取包。`default` 模块目标还会携带两个 x86_64 探针库；它们不提供播放能力，不能据此扩大支持架构。验证消费 HAP 时同时记录全部库与实际设备 ABI，正常 CI 候选必须为 ARM64 九库。
