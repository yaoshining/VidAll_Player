# 集成任务

- [x] 锁定 main 基线、兼容版来源，并复核宪章。
- [x] R1/R2 在主线复现并修复，保留主线终局场景。
- [x] R3 运行正常核心、原生及 ArkTS 验证，确认核心输入与构建流程。
- [x] R4 核对主线 PR 首轮 CI HAR、独立消费者及审查意见。最终提交的 iMac 复验记录与线程处理见 [PR #88](https://github.com/yaoshining/VidAll_Player/pull/88)。

主线旧实现已复现暂停 GL/SW 重绘缺失、Vulkan 重绑/释放、极短媒体 EOF 和新事件身份测试失败。移植后窗口 20 项、GL 12 项、SW 5 项以及原生/ArkTS 事件测试通过，含主线独有的终局拒绝场景。

主线正常核心宿主套件及 14 项 CTest、两项诊断 JS 均通过。PR 合并预览 `e28be4b243d4bbb0f223e6db30bb4061073b2119` 使用自托管 X64 iMac `yaoshiningdeiMac`。HAR 共 22,206,707 字节，SHA-256 为 `2e6abd6717b7ef7621dc6a9d69833be3ae43d010f0b5605d68235085fdaa4265`。解包复核八个锁定库均与 main 的 004-normal-core 输入逐字节一致。独立消费者九库校验、缺少公共 API 的编译负例和 Hypium 编译全部通过。[iMac PR 门禁](https://github.com/yaoshining/VidAll_Player/actions/runs/42405216760) · [PR 合并预览 HAR](https://github.com/yaoshining/VidAll_Player/actions/runs/42405216760/artifacts/13587660770)

首轮审查后的补充回归复现并修正了 SW 缓冲提交失败后的重绘、EOF 之后真实首帧的单次投递、终局计时因观察线程调度而偏短三条路径。另以受控线程交错验证 preparing 先于 EOF，以及重绑入队后调用 stop 能撤销待发事件。复验范围为 Player 主线及独立消费工程，历史设备回执对应 [#87](https://github.com/yaoshining/VidAll_Player/pull/87) 的兼容版。
