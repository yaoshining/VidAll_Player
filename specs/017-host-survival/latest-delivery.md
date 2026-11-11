# Spec 017 最新验收候选

此候选已完成 Player 实现、自动化回归和 CI 构建，**尚未完成真实 OHCodec/Vulkan、可听音频及 API 19 TV 正式文件入口验收，暂未提 PR**。普通播放仍优先零拷贝硬解；显式 `preserve-host` 保留主应用，全局终局后只有满足旧音频停止安全条件的新兼容实例可继续播放。

## 原始产物与来源

- 源提交：`01b2ad3a7041877b33e586b962a64385e10e027f`。
- [下载原始 CI HAR 附件](https://github.com/yaoshining/VidAll_Player/actions/runs/43024630552/artifacts/13856632429)，其中 `vidall_player.har` 未经消费端重打包。
- HAR SHA-256：`fddf4216751e9899594cc439fd304edf64c428f58b59b5d12055198237d350b3`。
- [HAR 构建](https://github.com/yaoshining/VidAll_Player/actions/runs/43024630552)：实际机器 `yaoshiningdeiMac`，self-hosted / macOS / X64；不是云端 Mac。
- mpv/libplacebo 核心在 MacBook Pro / Darwin arm64 交叉构建。mpv SHA-256：`5aa3d663b13289a7d6ab7ede6a0ac40dbd42b37642c9a93d0da11dc71f445b79`，恢复 ABI `0x00020000`。FFmpeg 沿用上游预编译恢复 SDK，本轮未修改或构建。
- [逐库 SHA-256 与来源记录](device-evidence/imac-delivery-01b2ad3.json)。HAR 仅支持完整 ARM64 播放，共九库。x86_64 旧探针不能用于播放；TV 如继续声明该架构，需另行补齐匹配 SDK/核心，不能静默删除声明或混入旧桥。

## 验证结果

| 层次 | 结果 | 边界 |
| --- | --- | --- |
| 宿主 | 91 项统一门禁、31 项来源正负例、14 项 CTest 和 2 项诊断 JS 通过 | 平台调用部分为替身 |
| [Ubuntu CI](https://github.com/yaoshining/VidAll_Player/actions/runs/43024633104) | 音频中断、旧回调隔离、音频生命周期、尺寸/旋转/播完及旧宿主检查通过 | 不证明系统焦点或真实声音 |
| iMac CI | HAR、独立消费者九库、缺失 API 负例、Hypium 编译通过 | Hypium 未在设备执行 |
| API 19 TV 模拟器，CI 原包 | standard / compatible 坏片返回、正常首帧、暂停/恢复、跳转和释放重开通过 | 实际均为 software/no |
| API 19 TV 模拟器，本地诊断包 | 全局终局注入后保持 PID，旧会话拒绝，新兼容会话连续两次播放有首帧 | 定时注入不是 GPU/fence 故障；诊断完整构建/静态检查通过，仍不能用于正式交付 |
| 目标真机 | 未完成 | 尚缺零拷贝故障、可听音频、系统打断和连续隔离上限验收；API 24 不能替代 API 19 TV |

最新模拟器记录分别见 [标准模式](device-evidence/api19-ci-standard-01b2ad3.json)、[显式兼容模式](device-evidence/api19-ci-compatible-01b2ad3.json) 和 [全局终局诊断](device-evidence/api19-injected-global-01b2ad3.json)。

## TV 迁移步骤

1. 核对原始 HAR 与九库哈希，整体替换旧 Player 产物及重复依赖；不在 TV 中修改或重打包 HAR。先解决 x86_64 支持边界。
2. 创建任何 Player 前调用 `initializePlayerRuntime(context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 })`；不要在终局通知中结束应用。
3. 新视频默认 standard；每次 `load` 的身份回执绑定稳定媒体 ID，只有 `onPlayerFault` 的 known 归属才能标记该视频。TV 持久化和重启策略由 [#372](https://github.com/yaoshining/vidall-tv/issues/372) 跟进，#371 手动选集暂停单独处理。
4. 全局终局后停止使用旧实例，保留旧 Surface，等待 recovery.ready 后创建 compatible 实例并使用新 Surface。只有实际首帧与音频确认后才提示兼容切换成功。普通坏片与可隔离会话故障沿用原恢复路径。
5. 按 [接入文档](../../docs/normal-core-integration.md) 处理容量错误和迟到回调；`PLAYER_EVENT_QUEUE_FULL` 是桥会话故障，释放后新建，不作为视频硬解失败标记。自动连播不能解除用户暂停或未结束的音频打断。
6. 从 API 19 TV 正式文件入口继续验证正常播放、音频打断/手动恢复、切集、退出重开、故障后返回、再播其他视频及连续故障上限，分别保存包哈希、PID、音画与原生日志。

若平台音频 Stop 永久阻塞或无法确认停止，当前实现仍须保持 pending/timeout，不能强行释放或假报续播成功。这是尚未消除的实际限制，不代表已放宽“全局故障后也能继续播放”的要求。

本候选新增 T035：renderer 已确认释放后，builder 清理失败或阻塞不再误挡兼容恢复；残留对象及槽预算仍保留。平台 Stop/Release 未确认的限制保持不变，设备上尚未注入 builder 故障；该边界目前由真实生产函数的宿主回归覆盖。
