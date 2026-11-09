# 平板基线与资源归还调查

## 设备与输入

- 云真机 MatePad Air WKI-W10，HarmonyOS 6.1.0.112，API 24。设备目录当时未提供 TV。API 19 TV 模拟器此前选择了软件解码，无法覆盖此处的 Vulkan 路径。
- 基线采用 main 提交 `794c5339982682fe06e2db1923c1cf0a140d21dd` 对应的播放器（完整提交见下方 CI 记录）。GitHub Actions 运行 [42612181532](https://github.com/yaoshining/VidAll_Player/actions/runs/42612181532) 产出的 HAR SHA-256 为 `bc0bbb1f78752cf3106e42ea04af404d6715583c8dffdc37556b69d925b8581e`。
- 真机使用本地签名的离线 VidAll_TV 测试 HAP，SHA-256 为 `91b1b6ee4c5c8f4819f9207ddb68a82af8d8b1c61ec5b15cf741eef1df3f9b8b`。对照了 HAR 的九个原生库。列表使用自制文件，选择后进入 VidAll_TV 播放页；验证的返回入口为页面上的「返回」。

## 坏 MP4 后再选正常片

坏文件破坏了容器索引，页面显示「播放未能继续」，点返回回到测试列表。另选有声音的正常片，观察到运动图案和变化的片内时间码。首次音频采样的三个窗口中播放位置从 0 推进到 4083 ms，系统输出幅度多次大于零。再次打开正常片也观察到了音画。播放器报告 `hw=active fmt=nv12 renderer=vulkan`。

在正常片日志中，`vo/gpu-next/ohcodec` 的同一个 buffer（seq 83502975）依次出现 acquire、hold（held=1，fence=76）、release-begin（fence=76）和 release-end（rc=0）。保留的日志含 121 条去重后的成功归还，两个播放线程来自进程 46085。该过滤记录始于健康片；坏文件在解封装阶段即已失败，未观察到该文件触发 GPU 排空错误，也没有捕获坏文件与正常片两端的 PID 对照。

## 逐帧归还与关闭排空

1. mpv 在解码器重置或关闭之前同步发送 `VOCTRL_OHCODEC_DRAIN`。在持有当前缓冲区时，Vulkan 实现依次调用 `pl_gpu_finish`、hold、提交 external release、`vkQueueWaitIdle` 和 NativeImage 归还。历史提交也可能需要等待。队列等待包在队列锁内，没有超时。仅给外围加超时无法证明 GPU 已完成。
2. 从封存源码直接编译 `mapper_release`、`ohcodec_drain`，用真管道 FD 和平台替身注入错误。主线 9 项中 6 项通过。排空已导出 fence、但队列等待失败时，FD 既没有转交给 Surface，也没有被关闭。候选补丁只关闭本地持有的 FD，原缓冲和导入对象继续保留。该用例从红转绿。
3. 逐帧替换时还有两项红测。hold 失败，或成功 hold 后导出 fence 失败，代码仍以 -1 归还缓冲并清除 busy。当前帧尚未取得有效的外部交接证明；下一帧此时已经提交 acquire，单纯提前 return 会覆盖旧帧的引用。会话隔离和上限仍待验证。
4. mpv 的 terminal 管理器关闭进程范围内的 OHCodec 创建入口并停住出错线程；VidAll_Player 的监视线程随后按 deadline 执行 `std::_Exit(86)`。独立宿主的旧门禁特意断言该行为。它和 TV 宿主要求的会话恢复存在直接冲突。

## FFmpeg 项目边界

主线使用的 FFmpeg 输入中 `libavcodec/ohdec.c` 的 SHA-256 为 `d7c4bcc960d54dcae930168a56fcd6cf2b064e8758294b9e6a98c80768f19499`。在 close 中先使输出失效，退役回调，等待已进入的回调与 token 操作，再 Stop 和 Destroy。Stop 或 Destroy 返回错误会设置进程级标志 `ohcodec_terminal_failure`。以后在同一进程进入 `oh_decode_create` 会在调用平台创建接口前返回 `AVERROR_EXTERNAL`。切换 NativeWindow 或新建 mpv 会话均不能解除此限制。此分支需交给 `ohos_ijkplayer` 处理；本次只读核对了输入，没有修改或重建 FFmpeg。

## 本地候选验证

两次独立构建得到相同的 libmpv SHA-256 `589434c76f3d44fcdeb668210ef5f4181a8d2d0dc367bf8e4b1b6dd7a0c7afbb`。来源锁和依赖审计通过；5 项输入派生测试通过；现有 normal-core 宿主门禁通过。针对 fence 所有权新增的 9 项回归中，7 项通过、2 项逐帧交接仍失败。本地库用于预验证，没有发布候选 HAR。

## 真机关闭错误注入

独立诊断 HAP `f56fc1ad88631243f7864f910c43fdfabe5444e0e4e4e718c90172a4caeb9388` 用离线配置构建。诊断版 mpv `5cf80c2ad1aa722bc708b06653c9024141ba87b492a7bf28be26cad95a4caeb2` 在真实队列等待返回成功后，仅一次将结果替换为 `VK_ERROR_DEVICE_LOST`。注入补丁在 `native/tests/ohcodec-fence/inject-wait.patch`，不在生产来源锁内。重放时在临时派生源码树应用该补丁，链接 `hilog_ndk.z`，用实际播放页播放正常硬解样片，关闭播放页并观察超过运行时的 3000 ms 期限。

样片有运动画面，退出播放页时列表短暂出现，随后回到了系统桌面。必须点应用图标重启。两次启动记录不同的 PID：

```text
00:05:20 FENCE_PROBE wait real=0 injected=-4 reason=2 pid=17419
00:06:14 FENCE_PROBE wait real=0 injected=-4 reason=2 pid=17751
```

reason=2 对应关闭。结果复现了应用进程退出，第三方驱动在这两次实验中的真实等待均返回成功。本实验不能推算真实设备丢失的发生率，且没有测出系统报告的退出码。源代码中受控退出使用 86。下一部片尚不能在该故障后的同一进程中完成验收。两轮云会话均已释放。
