# libmpv 播放器 HAR 实施计划

**分支**：`003-libmpv-player-har` | **日期**：2026-08-02 | **规格**：[spec.md](./spec.md)

**输入**：`spec.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`。

## 摘要

规划 `@vidall/player` 成为仅由 libmpv 驱动的受控本地 HAR。最终目标包含受控原生产物、内部 NAPI bridge、经真机证明的 XComponent/Surface 到 NativeWindow/EGL/GLES 渲染、最小 ArkTS 契约和本仓库独立 consumer fixture。

G1（目标 TV/API/复现）、G2（libmpv 联合审计）、G3（画面/线程/输入）均未关闭。本计划先安排阻断性研究和 spike，默认 No-Go。负责人未基于真机证据书面确认前，不交付 HAR、不声明播放或首帧支持、不生成真实实现任务。

## 技术背景与现有状态

- 工程是 HarmonyOS TV Stage 模型，主模块 `entry`；已有 `packages/vidall-player`、NAPI 打包 probe 和内存 `PlayerSession` 状态机。
- probe、内存状态机、构建或库加载成功、命令入队、Promise 成功和合成事件都不是播放、首帧或资源释放证据。
- native bridge、libmpv 供应链脚本和审计资产仅是研究输入，不能替代 G2 联合审计或 G3 真机 spike。
- 不修改 VidAll_TV；消费者验证只可在本仓库独立 fixture。OHPM 上传和公开发布不在范围。

## 技术上下文

**语言/版本**：ArkTS/ArkUI、C++、CMake、Hvigor/ohpm，遵循现有工程配置。

**主要依赖**：唯一播放内核 `libmpv`；XComponent、NativeWindow、EGL/GLES、NAPI 是待验证边界。

**存储**：来源锁、构建 manifest、SBOM、ELF/ABI 审计、能力证据、脱敏真机日志等文件型审计资料；不新增业务存储。

**测试**：TDD 自动化契约、单元、集成测试；不可自动化的首帧、画面生命周期和加载结果使用可重放 ARM64 TV 真机证据。

**目标平台**：HarmonyOS TV。API 15 是安装兼容下限，敏感/新增 API 必须核验 API 19，认证策略覆盖 API 19--22。具名 ARM64 TV/API 矩阵是 G1 待确认项。

**项目类型**：HAR 库和本仓库独立 fixture，不涉及 VidAll_TV。

**性能目标**：不预设帧率、首帧时间或资源数值；负责人须随设备/样本闭集确认阈值。UI 线程不得阻塞播放或渲染。

**约束**：只用 libmpv；禁止 AVPlayer 及回退；GPL-3.0-or-later 材料完整；未验证能力暂缓；公开能力只能由同候选、同样本、同设备规则的真机证据支撑。

## 宪章合规检查

### 研究前检查：仅允许阻断性研究

- 后续任务必须核验 API 19 可用性，并记录 API 15--18 的降级或拒绝策略；不假设候选 API 的版本行为。
- 真实状态必须来自 libmpv；所有权、线程、释放、generation、错误脱敏均需证实。
- 所有实现遵循先失败测试、最小实现、通过测试、重构；成功、边界、失败均覆盖。
- 协作者文档中文；仅本 feature 和后续 player/fixture 范围；不得改 VidAll_TV、`specs/001-*`、`specs/002-*`。

### 强制 No-Go 门禁

| 门禁 | 必须决策材料 | 默认停止条件 | 解锁条件 |
| --- | --- | --- | --- |
| G1：TV/API/复现 | 具名 ARM64 TV、API、样本数、跨设备规则、证据模板 | 未确认不声明设备/API/媒体支持 | 负责人确认且有指定真机记录 |
| G2：libmpv 联合审计 | 构建输入、加载位置/顺序/失败、HAR/私有层边界、ABI/ELF、GPL 材料 | 未确认或材料缺失不纳入/交付原生产物 | 负责人确认同候选完整审计链 |
| G3：画面/线程/输入 | attach/resize/detach/rebuild/release 时序、线程、样本闭集 | 未证实不公开稳定画面契约或首期输入 | 负责人确认真机 spike 和媒体闭集 |

### 设计后复检：通过但维持 No-Go

设计将三门禁置于首要阶段；数据和合约全部标注“暂定/待证实”；不含 AVPlayer、未验证媒体承诺、VidAll_TV 修改或公开发布。G1--G3 未关闭，真实实现继续阻断，符合规格和宪章。

## 分阶段架构与严格依赖

### 阶段 A：决策研究与 Spike（唯一可立即执行）

1. 固化 G1 设备、样本、事件、证据模板，收集负责人支持矩阵选择。
2. 盘点 G2 候选产物与来源，比较 HAR 随包、私有层、拒绝候选路径；仅产出差异和缺口审计。
3. 在负责人指定真机执行不预设所有权或线程模型的 G3 spike，记录画面代次、线程、NativeWindow/EGL/GLES 真路径、样本和释放。
4. 输出可重放步骤、候选 ID、环境、证据摘要、限制和 Go/No-Go 建议。
5. 三项负责人书面确认。任一未确认即停止，禁止生成真实功能任务。

### 阶段 B：受控供应链与分发骨架（依赖 A 全部 Go）

1. 依确认的加载策略建立候选 HAR 本地交付布局。
2. 用同一 `candidateId` 绑定来源锁、源码、构建、许可证、NOTICE、SBOM、ELF/ABI、可复现性和真机证据。
3. 先写准入校验，确保材料缺失、ABI/ELF 不符、无审批或未证实能力都会阻断。
4. 建立本仓库 fixture，只经公开接口验证受控本地导入；不触碰 VidAll_TV。

### 阶段 C：最小真实播放垂直切片（依赖 B 与 G3）

1. 先为 ArkTS 创建、画面 generation、无效画面拒绝、错误、释放后调用写失败测试。
2. 实现最小契约到唯一 libmpv 会话的 NAPI bridge；禁止 AVPlayer 和状态机伪造成功。
3. 依确认模型实现 XComponent/Surface 至 NativeWindow/EGL/GLES，验证 attach、resize、detach、重建、陈旧 generation、release。
4. 仅对批准媒体闭集实现 load/play/stop/release、真实事件和脱敏错误；其余明确拒绝或暂缓。

### 阶段 D：验证、能力收敛与准入（依赖 C）

1. 执行自动化成功、边界、失败、快速重复、释放后回调测试。
2. 在 G1 真机用同候选/同样本复现首帧、播放、错误、释放；首帧必须来自确认 NativeWindow/EGL/GLES 路径。
3. 仅将证据完整最小能力标为“已通过真机样本”；其余维持其他两态。
4. 复跑准入审计和 fixture；不上传 OHPM、不公开发布。

## 初版数据与合约

- 实体、状态、事件和审计关联：见 [data-model.md](./data-model.md)。
- ArkTS 公开和 NAPI 内部边界：见 [contracts/player-contract.md](./contracts/player-contract.md)。方法名只作任务草案；解锁后才可成为正式接口。
- 受控 HAR、准入、fixture 边界：见 [contracts/controlled-delivery-contract.md](./contracts/controlled-delivery-contract.md)。

## 构建与合规物料

每个 `candidateId` 必须同时关联 GPL-3.0-or-later 许可证、NOTICE、精确对应源码定位/摘要、来源锁、可执行构建脚本、manifest、SBOM、ABI/ELF/符号审计、双次构建摘要、加载边界审计、真机能力证据和负责人审批。

自动化检查材料、摘要、许可证策略、SBOM、ELF、可复现性和证据结构。加载策略、GPL 最终合规、支持矩阵、画面/线程及首帧真实性由人工审计和负责人确认。任一缺失即拒绝候选。

## TDD 与真机验证矩阵

| 类别 | 自动化测试先行 | 真机证据 | 阻断条件 |
| --- | --- | --- | --- |
| 导入边界 | fixture 公开导入，内部路径不可访问 | 受控安装/编译记录 | 需要 VidAll_TV 或内部模块 |
| 生命周期 | stop/release 幂等、释放后调用 | 资源与事件结束记录 | 崩溃、死锁、悬垂事件、残留画面 |
| 画面 | 尺寸、generation、attach/resize/detach/rebuild | 时序、线程、资源记录 | 所有权不明、旧画面接管、无真路径 |
| 媒体/首帧 | 批准/无效/未支持输入与错误映射 | 同候选/设备/样本的首帧、播放、失败 | probe/状态机/PixelMap 被当作证据 |
| 合规 | 材料、SBOM、ELF/ABI、能力状态 | 审计签收/负责人确认 | 材料或确认缺失 |

## 项目结构

```text
specs/003-libmpv-player-har/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── player-contract.md
│   └── controlled-delivery-contract.md
├── checklists/requirements.md
└── tasks.md                         # 仅在 G1--G3 全部关闭后生成

# 后续候选实现范围（G1--G3 前不可改动）
packages/vidall-player/
entry/src/main/cpp/
native/
release/
fixtures/libmpv-player-consumer/
```

**结构决定**：本次只创建 `specs/003-libmpv-player-har/` 下工件。后续 `speckit.tasks` 必须以 G1--G3 Go 记录为首个依赖，并依 B、C、D 顺序展开；不得更改 VidAll_TV、`specs/001-*`、`specs/002-*`。

## 复杂度追踪

| 约束 | 原因 | 拒绝的简化方案 |
| --- | --- | --- |
| libmpv、NAPI、图形与 HAR 联合门禁 | 规格要求真实内核、受控 GPL 分发、真机首帧 | probe、内存状态机、单库加载或 AVPlayer 回退均会伪造能力或违反约束 |
| 三项负责人决策前置 | 设备/API、加载审计、画面线程与输入共同决定可行接口 | 预先选择设备、加载位置或 Surface 语义会虚构结论 |
