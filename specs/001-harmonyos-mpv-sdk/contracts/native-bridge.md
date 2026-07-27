# 内部 ArkTS-NAPI 桥接契约

本契约只约束 `@vidall/player` HAR 内部 ArkTS 层与随候选制品交付的 NAPI/libmpv 实现；不得由 `Index.ets` 导出，也不得要求消费者导入 `entry`、私有 `.so`、NAPI、NativeWindow、EGL/GLES 或 libmpv。

## 会话与命令

- `create` 创建一个内部 `nativeSessionId`；该标识仅用于桥接关联、审计和脱敏日志，永不进入公开 ArkTS 对象或事件。
- `attachSurface`、`resizeSurface`、`detachSurface` 只接收受控 `componentId`、`generation`、宽和高。原生层在每个会话内持有 NativeWindow 和渲染资源；禁止进程全局 NativeWindow、EGL context 或渲染队列。
- `load`、`play`、`pause`、`seekRelative`、`seekPercent`、`setRate`、`setVolume`、`mute`、轨道选择、外挂字幕、字幕延迟、`stop` 与 `release` 均须有异步命令确认。Promise 成功仅表示原生层已接受或完成契约规定的命令阶段；播放、首帧和状态只能由后续真实内核事件确认。
- 每个命令携带单会话递增 `commandSequence`。切源或 release 使旧媒体/旧 generation 的待执行任务失效；不得用 ArkTS 模拟状态替代原生确认。
- 本 Issue 的 SMB 兼容路径仅为 localhost HTTP proxy lease，以 `leaseId` 与单会话递增 `epoch` 关联。切源、stop、release 或网络失败只能先发 `releaseRequested`；仅相同 `leaseId`/`epoch` 的业务层确认可发 `released`。超时与清理异常分别发 `expired`、`cleanupFailed`；重复请求幂等，旧 epoch 回调必须丢弃。桥接不得接受或拼接直接 `smb://`，也不得承诺当前 libmpv 具备该协议能力；未来 direct SMB 另立 Issue。

## 原生事件映射

- 事件只能来自 libmpv、渲染器或明确的桥接生命周期；ArkTS 不得在 `load()`、`play()` 或命令返回时伪造 `preparing`、`playing`、轨道、缓冲或首帧事件。
- 每个事件须带内部 `nativeSessionId`、`eventEpoch`、单会话严格递增 `sequence` 和关联 `surfaceGeneration`（无画面事件可为空）。经公开事件门面转发时保留 `eventEpoch`、`sequence` 和有效的 `surfaceGeneration`；ArkTS 仅接收当前会话、当前 epoch 与有效 generation 的事件，其他事件丢弃并可记录脱敏诊断。
- `firstFrame` 仅在当前 generation 的渲染器已成功提交一帧后发出；`file-loaded`、`play()` 命令成功或解码器创建均不等同于首帧。
- 事件至少映射：真实状态、位置/时长、缓冲、轨道、视频参数、音频参数、SMB proxy lease 状态、日志、关闭和结构化错误。所有 payload 必须可序列化、严格类型化并经脱敏处理。

## 释放与线程

- `release` 是一次性屏障：原子拒绝新命令，撤销 TSFN/ArkTS 回调，停止事件源，终止或隔离媒体与渲染任务，销毁该会话 NativeWindow/EGL/libmpv 资源，最后发出至多一个 `closed` 事件。
- `closed` 之后及 release Promise 完成之后不得再向 ArkTS 投递任何回调。重复 release 不创建原生任务且安全完成。
- UI 线程只提交短命令；libmpv 事件循环、网络、渲染和资源销毁不得阻塞 ArkUI UI 线程。NAPI/TSFN 失败必须转换为结构化 `native` 或 `lifecycle` 错误。

## 验证

- 桥接契约测试必须覆盖全部命令、命令确认、真实事件来源、乱序/旧 epoch 丢弃、surface 重建、释放屏障、TSFN 关闭、双会话隔离和结构化错误。
- ARM64 TV 真机证据必须证明创建、附着、加载、真实首帧、控制、重建与释放；模拟器只能作为兼容辅助，不能代替此门禁。
