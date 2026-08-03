# G3 Surface 真机 Spike 协议

## 前置条件

- 负责人指定具名 ARM64 TV、系统/API、候选 `candidateId` 和批准媒体样本闭集。
- G2 候选材料可供审计，但本协议不将材料存在视为播放证据。
- 运行时不得使用 `AVPlayer`、回退路径、内存状态机或合成成功事件。

## 逐步采集

1. 创建会话并记录 `sessionId`、`eventEpoch`、线程与初始资源计数。
2. attach：记录 component、generation、有效尺寸、NativeWindow 取得、EGL/GLES 初始化和每步线程。
3. resize：记录新旧尺寸、重新绑定或重建、资源计数和当前 generation。
4. load/play：仅使用批准样本；记录 libmpv 真实事件、NativeWindow/EGL/GLES 路径和首帧佐证。
5. detach：记录停止渲染、事件丢弃、旧 generation 失效和资源释放顺序。
6. destroy/rebuild：记录新旧画面交接；验证旧画面不渲染或接收回调。
7. stop/release：执行快速重复调用；记录线程结束、残留画面、释放后调用和陈旧回调处理。
8. 失败路径：使用无效画面和未批准输入；记录脱敏结构化错误，不得产生伪造首帧。

## 记录要求

每步关联 `candidateId`、设备/API、样本摘要、时间、线程、generation、事件序列、日志/截图/录像引用、失败、限制和结论。无 NativeWindow/EGL/GLES 真路径、所有权或线程模型不可解释、或未获负责人确认时均为 No-Go。
