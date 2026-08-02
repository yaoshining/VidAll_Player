# 初版数据模型

## 标记约定

本文所有带“暂定/待证实”的字段、状态和关系仅用于后续 spike、测试和任务拆解，不能直接视为实现承诺或公开支持声明。

## 受控 HAR 候选

| 字段 | 说明 | 校验 |
| --- | --- | --- |
| `candidateId` | 候选唯一标识 | 必填，关联全部审计和真机证据 |
| `packageVersion` | HAR 版本 | 必填，不等同于支持声明 |
| `sourceCommit` | 精确源提交 | 必填，可追溯 |
| `deliveryStatus` | `draft`、`blocked`、`approved`、`rejected` | 未关闭三门禁时只能为 `draft` 或 `blocked` |
| `kernel` | 固定值 `libmpv` | 非 `libmpv` 或任何 AVPlayer 回退即拒绝 |
| `loadingStrategy` | 暂定：`har-bundled`、`private-native-layer` 或未确定 | 需决策 2 确认 |
| `abi` | 暂定目标 ABI | 必须由 ELF 审计和负责人确认 |

## 播放器会话（暂定/待证实）

| 字段 | 说明 | 校验 |
| --- | --- | --- |
| `sessionId` | 会话标识 | 每次创建唯一；不暴露原生句柄 |
| `state` | `idle`、`preparing`、`playing`、`paused`、`buffering`、`completed`、`error`、`released` | 单一可追踪状态源；真实内核事件才可推进播放相关状态 |
| `surfaceGeneration` | 当前画面 generation | 只接受当前有效 generation 的事件 |
| `eventEpoch` | 事件批次/生命周期纪元 | release 后递增或关闭；旧事件必须丢弃 |
| `sequence` | 会话内事件序号 | 单调递增，用于审计顺序 |
| `mediaSampleId` | 首期媒体样本 ID | 仅负责人确认的闭集可用于真机结论 |
| `releasedAt` | 释放记录 | 一旦设置，控制操作稳定失败或按明确幂等规则完成 |

### 状态转换（暂定/待证实）

- `idle -> preparing`：有效画面与已批准输入均存在，且真实原生会话确认开始准备。
- `preparing -> playing`：目标真机的真实内核事件与首帧证据支持；不得由命令入队或内存状态机触发。
- `playing|paused|buffering|completed|error -> released`：释放完成后不再向消费方发出会话事件。
- 任意非 `released` 状态可进入 `error`；错误必须分类、脱敏并说明可重试性。
- `released` 为终态；后续控制不得报告播放、暂停或首帧成功。

## 播放画面（暂定/待证实）

| 字段 | 说明 | 校验 |
| --- | --- | --- |
| `componentId` | 消费方 XComponent 标识 | 不暴露系统底层对象 |
| `generation` | 画面生命周期代次 | attach、detach、重建顺序需由 spike 证明 |
| `width` / `height` | 当前尺寸 | 零或负值不得作为可播放画面 |
| `availability` | `attached`、`detached`、`destroyed` | 语义及所有权待决策 3 确认 |
| `nativeBinding` | 内部关联（不公开） | NativeWindow/EGL/GLES 所有权和线程模型待证实 |

## 事件和错误（暂定/待证实）

| 实体 | 字段 | 规则 |
| --- | --- | --- |
| `PlayerEvent` | `sessionId`、`eventEpoch`、`sequence`、`type`、`surfaceGeneration`、`occurredAt` | 归属明确；陈旧 generation 或 released 会话事件必须忽略 |
| `FirstFrameEvent` | 事件通用字段、`evidenceRef`（内部审计字段） | 对外成功只能在真机证据链完整后声明 |
| `PlayerError` | `code`、`category`、`retryable`、`message`、`sessionId` | 不得包含完整媒体地址、原生句柄或敏感日志 |

错误分类暂定为 `INPUT_INVALID`、`SURFACE_UNAVAILABLE`、`LIFECYCLE_INVALID`、`NATIVE_PLAYBACK_FAILED`、`RELEASED`、`FEATURE_UNSUPPORTED`。分类、重试语义和映射关系需经真实 bridge 及真机失败路径验证。

## 能力证据

| 字段 | 说明 | 校验 |
| --- | --- | --- |
| `capability` | 被评估的最小能力 | 不能泛化为全部 mpv 能力 |
| `status` | 三态结论 | `已构建待验证` 绝不等于支持 |
| `candidateId` | 关联 HAR 候选 | 必填 |
| `device` | 机型、ABI、系统/API、匿名标识 | 决策 1 确认后才可填为支持基线 |
| `sample` | 样本 ID、摘要、脱敏输入类别 | 必填，必须属于批准闭集 |
| `evidenceRefs` | 日志、录像、截图、审计结果引用 | 真机结论必填 |
| `limitations` | 已知限制 | 必填；未验证能力明确暂缓 |
| `approvalRef` | 负责人书面确认引用 | 任何首期承诺必填 |

## 分发材料包

材料包与 `candidateId` 一一关联，至少包括：GPL-3.0-or-later 许可证、NOTICE、精确对应源码定位、可执行构建脚本、来源锁、构建 manifest、SBOM、ELF/ABI 审计、可复现构建报告、真机能力证据和负责人准入结论。缺少任一材料，`deliveryStatus` 必须为 `blocked` 或 `rejected`。
