# 数据模型：VidAll_Player 可发布组件库

## 播放器会话

| 字段 | 类型 | 规则 |
|---|---|---|
| `sessionId` | `string` | SDK 内唯一，日志只记录短关联标识。 |
| `nativeSessionId` | `opaque` | 仅 ArkTS-NAPI 桥接关联使用；永不进入公开对象、事件或日志。 |
| `state` | `PlayerState` | 只允许 `idle`、`preparing`、`playing`、`paused`、`buffering`、`completed`、`error`、`released`，且只能由真实原生事件确认。 |
| `surfaceGeneration` | `number` | 每次附着递增，旧世代渲染任务与事件必须丢弃。 |
| `eventEpoch` | `number` | 原生会话重建或切源时递增，并公开在每条 `PlayerEvent` 中；桥接拒绝不匹配 epoch 的回调。Surface 重建仅递增 `surfaceGeneration`。 |
| `firstFrame` | `none` \| `submitted` | 仅当前 generation 的渲染器提交一帧后才为 `submitted`；不是 `file-loaded` 或命令成功。 |
| `media` | `MediaSource?` | 切源前先终止旧媒体资源。 |
| `tracks` | `PlayerTrack[]` | 只由原生媒体事件更新。 |
| `nativeHandle` | `opaque` | 仅 NAPI 内部可见，不进入 ArkTS 公开对象、事件或日志。 |
| `commandSequence` | `number` | 每会话递增；原生队列按此序列串行处理命令。 |
| `eventSequence` | `number` | 每会话严格递增；ArkTS 丢弃旧 epoch、旧 generation、旧序号或已关闭会话的事件。 |
| `releasePhase` | `open` \| `closing` \| `closed` | 首次释放只能从 `open` 转 `closing`；资源回收完毕、回调屏障生效后转 `closed`。 |

状态迁移：`idle -> preparing -> playing|error`；`playing <-> paused`；`playing|paused -> buffering -> playing|paused|error`；活动状态可转 `completed|idle|error`；任意未释放状态可转 `released`，且 `released` 为终态。`releasePhase=closing|closed` 时拒绝新命令；重复 `release` 不创建新任务。

## 媒体、事件与错误

| 实体 | 核心字段 | 规则 |
|---|---|---|
| `MediaSource` | `kind`、`uri`、受控 `headers`、外挂音频/字幕 | 仅 localFile/http/https/hls/dash/smb；禁止 URL 用户信息；认证头只可在同受信任范围的重定向内传递。 |
| `WebDavServiceConfig` | 显示名、服务端地址、认证状态、安全存储引用 | 不保存/返回明文密码；地址和认证上下文写日志前脱敏。 |
| `PlayerTrack` | `id`、类型、语言、标题、选择状态、渲染结论 | 将字幕“可识别”与“正确渲染”分离。 |
| `PlayerEvent` | 会话、单调 `sequence`、`eventEpoch`、可选 `surfaceGeneration`、类型、脱敏 payload | 覆盖真实状态、真实首帧、进度、缓存、轨道、参数、日志、错误和关闭；不含 native handle。 |
| `NativeCommandResult` | `commandSequence`、接受/完成阶段、稳定错误或无错误 | Promise 成功不推断播放或首帧；状态只由后续原生事件确认。 |
| `PlayerError` | 域、稳定码、中文信息、可重试、脱敏上下文 | 不含密码、Authorization、令牌、完整路径或敏感查询。 |

## 发布证据

| 实体 | 核心字段 | 不变量 |
|---|---|---|
| `BuildRecord` | 源提交、完整锁定摘要、工具链/镜像摘要、补丁、构建开关、产物 SHA | 输入与输出可追溯；锁定须覆盖 libmpv、FFmpeg 和全部传递依赖。 |
| `ElfAudit` | 文件 SHA、架构、ABI、SONAME、NEEDED、导出/禁止符号、审计工具版本 | 必须为 `aarch64-linux-ohos` 且匹配动态依赖、符号白名单。 |
| `CapabilityEvidence` | 版本、锁定摘要、匿名设备、API 层、匿名样本、三态、指标、限制 | 构建成功不能替代真机结论；三态只可为“已通过真机样本”“已构建待验证”“不支持或暂缓”。 |
| `VerificationArtifact` | 验证构件 ID、制品、来源证明、SHA、ABI、装入/consumer-smoke 结果 | 可安装以取得真机证据，但不得上传、宣传或标记为候选/发布。 |
| `ReleaseCandidate` | tag、候选 ID、制品、SBOM、LICENSE/NOTICE、审计、能力证据、状态 | 只能由证据齐全的 `VerificationArtifact` 派生；所有附件共享来源证明与 SHA；状态为 `candidate`、`failed` 或 `published`。 |
| `PublicationReceipt` | 两渠道回读、批准引用、时间、差异摘要 | 两边版本、来源提交、HAR SHA、SBOM SHA 与发布说明摘要完全一致才可为 `published`；不在仓库记录凭据或人员身份。 |
| `IjkCompatibilityRow` | IJK 基线行为、SDK 契约、消费方开关、独立样例、设备/样本、三态、证据 | 只定义目标，不改变 VidAll_TV；异常、性能不达标、泄漏或未验证均回退 `ijk`。 |
