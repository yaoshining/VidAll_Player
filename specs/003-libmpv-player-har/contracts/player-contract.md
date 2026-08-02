# ArkTS 与 NAPI 契约边界（暂定/待证实）

## 适用范围

本契约是后续 spike 和任务的接口边界草案，不是可用 API 的发布声明。只有目标真机样本、三项负责人确认和受控 HAR 准入均完成后，才可把最小经证实子集提升为公开 `playerContract`。

## ArkTS 公开边界

消费方只可经 `@vidall/player` 的公开 ArkTS 入口创建会话、提供画面描述、发起控制和订阅事件。不得接触 NAPI 模块名、原生句柄、NativeWindow、EGL/GLES 对象、原生线程或 libmpv 对象。

| 操作（暂定名称） | 输入 | 暂定规则 | 当前状态 |
| --- | --- | --- | --- |
| `createPlayer()` | 无 | 创建逻辑会话，不等同于原生播放可用 | 已构建待验证 |
| `attachSurface(surface)` | `componentId`、`generation`、尺寸 | 仅记录/绑定候选画面；所有权待 spike 证明 | 已构建待验证 |
| `resizeSurface(surface)` | 当前 generation 与尺寸 | 原地更新或重建语义未定；无对应原生证据时不得承诺 | 已构建待验证 |
| `detachSurface(generation)` | generation | 旧 generation 不得再获得渲染或事件 | 已构建待验证 |
| `load(input)` / `play()` | 已批准闭集媒体输入 | 无有效画面、未批准输入或未关闭门禁时必须拒绝/暂缓 | 不支持或暂缓 |
| `stop()` | 无 | 幂等语义须由真实会话验证 | 已构建待验证 |
| `release()` | 无 | 必须可重复调用；释放后不可报告播放或首帧成功 | 已构建待验证 |
| `subscribe(listener)` | 类型化监听器 | 仅转发真实会话事件；禁止合成成功事件 | 已构建待验证 |

首期不支持或暂缓：脚本、滤镜、录制、流捕获、截图，以及任何未进入负责人批准媒体闭集的协议、容器、编码、轨道或控制。

## ArkTS 事件与错误

暂定事件均应带 `sessionId`、`eventEpoch`、`sequence`、`surfaceGeneration` 和时间。消费方只处理当前会话、当前 epoch 和当前 generation 的事件。`firstFrame` 只能表示已经由目标真机证据链确认的真实 libmpv 渲染结果；在此之前不得对外暴露为成功事件。

错误需使用结构化、脱敏且含 `retryable` 的类型化结果；至少区分输入无效、画面不可用、生命周期非法、原生播放失败、已释放、能力暂缓。完整媒体地址、原生句柄、敏感日志和内部加载路径不得进入公开错误。

## NAPI 内部边界（暂定/待证实）

NAPI 仅是 ArkTS 与唯一 libmpv 内核的内部桥接候选。它必须：

- 明确 ArkTS/UI、NAPI 回调、mpv 事件循环和渲染线程边界；UI 线程不得承担阻塞播放或渲染工作。
- 接收并验证会话/画面 generation；释放后禁止向 ArkTS 投递陈旧回调。
- 不创建、调用、包装或回退 HarmonyOS `AVPlayer`。
- 只在决策 2 的加载策略、ABI/ELF/GPL 联合审计获确认后加载原生产物。
- 只在决策 3 的所有权与线程 spike 获确认后把 XComponent/Surface 关联到 NativeWindow/EGL/GLES。

任何 NAPI probe 成功、模块加载成功或命令入队成功，均不构成播放、首帧、资源释放或公开契约可用的证据。
