# 当前 No-Go 基线

## 结论

当前候选状态为 `blocked`。G1、G2、G3 均未获得负责人书面 Go 确认，因此不得创建或修改 HAR、`libmpv.so`、NAPI bridge、播放器实现、consumer fixture 实现，亦不得修改 VidAll_TV。

## 强制边界

- 唯一允许的播放内核是 `libmpv`；禁止引入、调用或回退到 HarmonyOS `AVPlayer`。
- NAPI probe、内存状态机、构建成功、库加载成功、命令入队、Promise 成功和合成事件均不构成播放、首帧或资源释放证据。
- `libmpv.so` 未完成与加载边界、ABI/ELF、GPL 精确对应源码的联合审计和负责人确认前，不得纳入或交付候选 HAR。
- 未取得 NativeWindow/EGL/GLES 真路径、画面生命周期和线程模型的目标真机证据前，不得声明画面渲染、首帧、播放或释放安全。
- OHPM 上传、公开发布以及对 VidAll_TV 的修改、构建、提交或依赖均不在本功能范围内。

## 允许工作

仅允许完成本目录下的研究、证据模板、审计模板、No-Go 验证和负责人决策归档。所有结论只可使用 `已构建待验证` 或 `不支持或暂缓`，不得表述为已支持。
