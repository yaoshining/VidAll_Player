# Spec 017 最新验收候选

**2026-11-13 更新：T046 修复版 62e4e3f 已取得并核验完整 iMac CI HAR；尚未完成该 CI 原包的平板音频复验，不能作为已验收交付。** T045 在 API24 平板复现了系统 PAUSE 未接入及验收页时长断言错误，已按 TDD 修复。当前94项宿主门禁、五组生产音频函数回归、六套验收工具回归与 iMac/Ubuntu CI 通过；实际内录音轨、现代系统焦点复验及 API19 TV 正式文件入口仍未完成，暂未提 PR。详见 [T046 修复记录](device-evidence/t046-modern-audio/README.md)。普通播放保留零拷贝硬解。

## 原始产物与来源

- 源提交：`62e4e3f8d9648f60713e03d182b2e0f45d923118`。
- [下载原始 CI HAR 附件](https://github.com/yaoshining/VidAll_Player/actions/runs/43237406546/artifacts/13953676510)，其中 `vidall_player.har` 未经消费端重打包。
- HAR SHA-256：`a419c1545680d48ab22983472a8c8ca3311a58bf5904cebdabfde2394e40b704`。
- [HAR 构建](https://github.com/yaoshining/VidAll_Player/actions/runs/43237406546)：实际机器 `yaoshiningdeiMac`，self-hosted / macOS / X64；不是云端 Mac。
- mpv/libplacebo 核心在 MacBook Pro / Darwin arm64 交叉构建。mpv SHA-256：`b81a0f2d54cc01defcc26849cb0e65404936528fc16f57ddf08b847591627086`，恢复 ABI `0x00020000`。FFmpeg 沿用上游预编译恢复 SDK，本轮未修改或构建。
- [逐库 SHA-256 与来源记录](device-evidence/imac-delivery-62e4e3f.json)。HAR 仅支持完整 ARM64 播放，共九库。x86_64 旧探针不能用于播放；TV 如继续声明该架构，需另行补齐匹配 SDK/核心，不能静默删除声明或混入旧桥。

## 验证结果

| 层次 | 结果 | 边界 |
| --- | --- | --- |
| T046 本地宿主 | 94 项统一门禁、五组音频生产函数、六套验收工具回归通过 | 平台调用部分为替身 |
| 62e4e3f [Ubuntu CI](https://github.com/yaoshining/VidAll_Player/actions/runs/43237652695) | 音频中断、旧回调隔离、音频生命周期、尺寸/旋转/播完及旧宿主检查通过 | 不证明系统焦点或真实声音 |
| iMac CI | HAR、独立消费者九库、缺失 API 负例、Hypium 编译通过 | Hypium 未在设备执行 |
| API 19 TV 模拟器，62e4e3f CI 原包 | 同PID坏片返回、两个首帧、暂停/恢复、跳转与释放重开通过 | software/no，见[当前原包记录](device-evidence/t046-modern-audio/api19-ci-software.json)；无真实声音或硬解结论 |
| API 19 TV 模拟器，d4a059b 历史 CI 原包 | standard / compatible 坏片返回、正常首帧、暂停/恢复、跳转和释放重开通过 | 实际均为 software/no |
| API 19 TV 模拟器，本地诊断包 | 全局终局注入后保持 PID，旧会话拒绝，新兼容会话连续两次播放有首帧 | 定时注入不是 GPU/fence 故障；诊断完整构建/静态检查通过，仍不能用于正式交付 |
| API24 云平板，T044 本地完整包 | 真实 OHCodec/Vulkan 关闭注入、同进程返回/晚关闭/隔离上限、全局后兼容续播及普通回归通过 | 尚缺可听音频、系统焦点中断和新CI产物复验；API24不能替代API19 TV |
| T045 API24 云平板旧包 | 焦点 SYSTEM_PAUSE_MISSING、普通流程 DIAGNOSTIC_UNAVAILABLE 失败，已据此修复 | 失败记录保留；不能算 T046 设备通过 |
| API19 TV 正式入口 | 未完成 | 等正式HAR由消费端接入后继续验收 |

历史 d4a059b 模拟器记录分别见 [标准模式](device-evidence/api19-ci-standard-d4a059b.json)、[显式兼容模式](device-evidence/api19-ci-compatible-d4a059b.json) 和 [全局终局诊断](device-evidence/api19-injected-global-d4a059b.json)。

## TV 迁移步骤

1. 核对原始 HAR 与九库哈希，整体替换旧 Player 产物及重复依赖；不在 TV 中修改或重打包 HAR。先解决 x86_64 支持边界。
2. 创建任何 Player 前调用 `initializePlayerRuntime(context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 })`；不要在终局通知中结束应用。
3. 新视频默认 standard；每次 `load` 的身份回执绑定稳定媒体 ID，只有 `onPlayerFault` 的 known 归属才能标记该视频。TV 持久化和重启策略由 [#372](https://github.com/yaoshining/vidall-tv/issues/372) 跟进，#371 手动选集暂停单独处理。
4. 全局终局后停止使用旧实例，保留旧 Surface，等待 recovery.ready 后创建 compatible 实例并使用新 Surface。只有实际首帧与音频确认后才提示兼容切换成功。普通坏片与可隔离会话故障沿用原恢复路径。
5. 按 [接入文档](../../docs/normal-core-integration.md) 处理容量错误和迟到回调；`PLAYER_EVENT_QUEUE_FULL` 是桥会话故障，释放后新建，不作为视频硬解失败标记。自动连播不能解除用户暂停或未结束的音频打断。
6. 从 API 19 TV 正式文件入口继续验证正常播放、音频打断/手动恢复、切集、退出重开、故障后返回、再播其他视频及连续故障上限，分别保存包哈希、PID、音画与原生日志。

若平台音频 Stop 永久阻塞或无法确认停止，当前实现仍须保持 pending/timeout，不能强行释放或假报续播成功。这是尚未消除的实际限制，不代表已放宽“全局故障后也能继续播放”的要求。

本候选保留 T035：renderer 已确认释放后，builder 清理失败或阻塞不再误挡兼容恢复；残留对象及槽预算仍保留。平台 Stop/Release 未确认的限制保持不变，设备上尚未注入 builder 故障；该边界目前由真实生产函数的宿主回归覆盖。

本候选另含 T041：音频 Stop 返回错误后仍查询真实状态，仅明确 STOPPED 才确认静止；状态仍运行、查询失败及调用未返回均不能放行。已通过生产函数正负例和当前源码的 Ubuntu 回归，设备未注入该特定平台错误。T039/T040 的[完整宿主门禁与最终收证](https://github.com/yaoshining/VidAll_Player/actions/runs/43038250441)也已通过。
