# VidAll_Player 故障恢复交付：四项待办

更新时间：2026-11-14。当前进度：**0 / 4 完成**。

日常查看及勾选入口：[Todoist「Player」](https://app.todoist.com/app/project/player-6j294wJX64V7p54G)。本文件是仓库内同步总览；详细实现任务保留在 [tasks.md](tasks.md)，当前包与验收边界见 [latest-delivery.md](latest-delivery.md)。

目标：播放器故障时主应用和列表保持可用，安全恢复后继续播放；未标记视频优先硬解，问题视频单独记忆兼容选择。这是 #91、#92 合并后的 Spec017 后续工作，不是重新修复已关闭的 #89。

- [ ] **1．修复当前 API24 音频打断失败。** 当前云平板重复出现 `SYSTEM_PAUSE_MISSING`。查清系统焦点、原生回调与 Player 状态之间的断点，先补回归再修复；实机确认打断时暂停，解除后保持暂停，用户按一次播放恢复进度和声音。对应 T017/T045/T046。完成日期与证据：待补。
- [ ] **2．完成当前版本两组故障恢复音画验收。** 关闭故障、全局故障后均能在同进程返回列表，再播其他视频有运动画面和声音；旧音消失、不混播，连续故障达到隔离上限行为明确。记录包哈希、PID、实际 OHCodec/Vulkan 路径与音轨。新版诊断包已准备，完整实机验收尚未完成。对应 T009/T013/T018/T045。完成日期与证据：待补。
- [ ] **3．解决旧音频停止或释放永久挂起的边界。** 目前无法确认旧音频安全停止时仍会保持 pending/timeout，不能保证安全续播。须在不退出主应用、不强行释放未知资源、不绕过保护、不无限等待或扩张资源的前提下验证安全恢复；若当前架构无法满足，先报告限制与备选方案，用户决定前保持未完成。对应 R3/R4、T009/T017。完成日期与证据：待补。
- [ ] **4．提交到 main 的 PR、完成 CI 交付及 TV 正式接入回归。** 前三项完成且达到既定真机门槛后提 PR；审查、检查通过后合并，交付原始完整 CI HAR、源提交、实际构建机器、HAR/九库哈希、架构边界及迁移步骤。由 TV 按 [#372](https://github.com/yaoshining/vidall-tv/issues/372) 接入，从 API19 TV 正式文件入口完成回归；ARM64/x86_64 差异明确处理，不混旧桥或静默删除架构。对应 T006/T007。完成日期与证据：待补。

## 更新约定

执行本任务时每完成一项，同步勾选 Todoist、本清单和详细 tasks 中的对应任务，填写完成日期、源提交、验收链接。部分完成、仅构建/CI通过或其他设备通过不提前勾选。第4项只有交付和消费端正式回归均完成才勾选；中间进度写在对应项下。本清单不设置定时轮询，不再维护 Linear。

Todoist 任务 ID（按上方四项顺序）：`6j295Q448pg9QX8p`、`6j295Q6Rx6RQgxvG`、`6j295Q6WFFfJ74fG`、`6j295Q7jffjHC3qp`。后续会话复用这些条目。

所属分区：**Spec017 · 故障恢复交付**，分区 ID：`6j296fXM7c27Vg7p`。
负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)，thread ID：`01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`，host：`local`；归属更新：2026-11-13。会话名称沿用历史标题，当前工作为 Spec017。交接时同步更新 Todoist 分区及步骤的负责会话。

## 已完成的历史

- 北京时间2026-11-09 18:35：[PR #91](https://github.com/yaoshining/VidAll_Player/pull/91) 合入 main，[#89](https://github.com/yaoshining/VidAll_Player/issues/89) 随之关闭。
- 北京时间2026-11-11 08:39：[PR #92](https://github.com/yaoshining/VidAll_Player/pull/92) 合入 main，增加单会话故障隔离。
- 当前分支：`codex/host-survival-contract`；生产候选：`62e4e3f`；截至本清单建立，最新设备证据提交：`38fb2b8`，尚无 Spec017 新 PR。

API24 平板不替代 API19 TV 正式入口验收；FFmpeg 和 VidAll_TV 的代码不在本 Player 任务内修改。永久平台挂起仍是未解决限制，不能因列入待办而视为需求已满足。


2026-11-13最新进展：实际HarmonyOS7.0.0.111 Air（不是API24）在坏片返回、正常视频首帧后Cpp Crash，尚未触发Alarm。第1项先处理该新增阻塞；T049补独立诊断的崩溃收证/音轨导出，四项均未完成。详情见[本轮失败记录](device-evidence/t049-native-crash.md)。

2026-11-14进展：T050修复现代OHAudio写入/中断共用userData的AO/token冲突，真实注册语义先红后绿。干净上游派生的7组音频回归、94项完整宿主和本地完整九库HAR核验通过；准备推送iMac CI。API24焦点和API26崩溃未复验，仍为0/4。T049已在API24保存实际内录到设备个人目录，但尚未取回音轨，不能勾选声音通过。
