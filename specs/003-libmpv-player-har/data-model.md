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
| `hardwareDecoding` | 播放选项：`'auto'`（默认，GL 路径下自动选中 ohcodec 硬解）或 `'disabled'`（强制 mpv `hwdec=no` 软件解码） | 通过公开 `PlayerOptions.hardwareDecoding` 下发到 native；是否激活以真机 `hwdec-current` 为准；待证实 |
| `releasedAt` | 释放记录 | 一旦设置，控制操作稳定失败或按明确幂等规则完成 |

### 轨道元数据（暂定/待证实）

消费方（vidall-tv 等）需要展示与系统 AVPlayer 对等的轨道详情。mpv `track-list` 属性提供完整的轨道元数据，当前仅编码 `id/kind/language/title/selected`，大量字段被丢弃。以下为拟扩展的 `PlayerTrack` 字段及其 mpv 属性来源：

| 字段 | 类型 | mpv 属性 | 说明 |
| --- | --- | --- | --- |
| `id` | number | `track-list/N/id` | 已暴露 |
| `kind` | `'audio'\|'video'\|'subtitle'` | `track-list/N/type` | 已暴露 |
| `language` | string? | `track-list/N/lang` | 已暴露 |
| `title` | string? | `track-list/N/title` | 已暴露 |
| `selected` | boolean | `track-list/N/default` | 已暴露 |
| `codec` | string? | `track-list/N/codec` | 编码名称（h264/aac/ass 等） |
| `profile` | string? | `track-list/N/profile` | 配置文件（High/LC 等） |
| `level` | number? | `track-list/N/level` | 等级（41 等） |
| `bitrate` | number? | `track-list/N/demux-bitrate` | 码率（bps） |
| `isDefault` | boolean? | `track-list/N/default` | 是否默认轨道 |
| `isForced` | boolean? | `track-list/N/forced` | 是否强制轨道 |
| **视频轨道特有** | | | |
| `resolution` | string? | `dwidth`×`dheight` | 分辨率（如 "1920x1080"） |
| `fps` | number? | `track-list/N/demux-fps` | 帧率 |
| `aspectRatio` | string? | `video-params/aspect` | 宽高比（如 "16:9"） |
| `isInterlaced` | boolean? | `video-params/interlaced` | 是否隔行扫描 |
| **音频轨道特有** | | | |
| `sampleRate` | number? | `track-list/N/demux-samplerate` | 采样率（Hz） |
| `channels` | number? | `track-list/N/demux-channels` | 声道数 |
| `channelLayout` | string? | `track-list/N/demux-channels` | 声道布局（stereo/5.1 等） |

### 视频参数元数据（暂定/待证实）

`VideoParams` 已有 `width/height/hardwareDecoding`，以下为拟扩展的色彩与格式字段：

| 字段 | 类型 | mpv 属性 | 说明 |
| --- | --- | --- | --- |
| `width` | number | `dwidth` | 已暴露 |
| `height` | number | `dheight` | 已暴露 |
| `hardwareDecoding` | `'active'\|'fallback'\|'unavailable'?` | `hwdec-current` | 已暴露（真机验证通过） |
| `pixelFormat` | string? | `video-params/pixfmt` | 像素格式（yuv420p 等） |
| `bitDepth` | number? | `video-params/bits-per-component` | 位深度（8/10/12） |
| `colorPrimaries` | string? | `video-params/primaries` | 基色（bt709/bt2020 等） |
| `colorTransfer` | string? | `video-params/transfer` | 传输特性（bt709/smrp428/pq 等） |
| `colorMatrix` | string? | `video-params/matrix` | 色偏矩阵（bt709/bt2020nc 等） |
| `videoRange` | string? | `video-params/sig-peak` + 推断 | 视频范围（SDR/HDR/Unknown） |
| `fps` | number? | `track-list/N/demux-fps`（视频轨道） | 帧率 |
| `rotation` | number? | `video-params/rotate` | 旋转角度 |
| `aspectRatio` | string? | `video-params/aspect` | 显示宽高比 |
| `isInterlaced` | boolean? | `video-params/interlaced` | 是否隔行扫描 |

### 音频参数元数据（暂定/待证实）

`AudioParams` 拟扩展字段：

| 字段 | 类型 | mpv 属性 | 说明 |
| --- | --- | --- | --- |
| `sampleRate` | number? | `track-list/N/demux-samplerate` | 采样率 |
| `channels` | number? | `track-list/N/demux-channels` | 声道数 |
| `channelLayout` | string? | `track-list/N/demux-channels` | 声道布局 |
| `codec` | string? | `track-list/N/codec` | 编码名称 |

### 原生编码方案（暂定/待证实）

扩展后的元数据量增大，当前 `\x1e`/`\x1f` 分隔符编码方案需评估是否仍适用：

- **方案 A（沿用分隔符编码）**：扩展 `EncodeTrackList` 增加 `\x1f` 分隔的 key=value 对，每个轨道一条记录。优点：不改动 Event 结构体；缺点：编码复杂度增加，解析容错性差。
- **方案 B（JSON 编码）**：message 改为 JSON 字符串。优点：结构清晰、扩展性强；缺点：native 层需引入 JSON 序列化，消息体积增大。
- **方案 C（新增事件类型）**：将轨道详情和视频参数分别拆为独立事件类型（如 `trackDetail`、`colorParams`）。优点：职责分离；缺点：增加事件类型，消费方需处理多事件时序。

视频参数元数据编码可复用 videoParams message 的 `|` 扩展模式：`"宽x高|hwdec|pixfmt|bitDepth|primaries|transfer|matrix|videoRange|fps|rotation|aspectRatio|interlaced|colorLevels|bitrate|renderBackend"`。其中 `renderBackend`（issue #77，最后一位，纯值）为渲染后端的字符串映射（`vulkan`/`opengles`/`software`/`unavailable`），反映 `SelectRenderBackend()` 的实际选择；Dolby Vision 由 `matrix==dolbyvision`/`pixfmt` 识别，渲染后端供 App 端做 DV 渲染能力提示（`vulkan`=vo_gpu_next 可 reshape，SW/GL 不可）。

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
