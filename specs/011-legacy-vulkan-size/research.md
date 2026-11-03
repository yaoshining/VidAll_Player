# 研究与决策

- 根因：Vulkan 初始化后的本地 RenderLoop 已返回，旧 Resize 只置 geometryDirty 并唤醒该循环，不能通知核心/VO。采用已有 `ohos-surface-size` 属性；旧 libmpv 已含该支持，不需重建或升级核心。
- 旧基线选择：用户明确要求沿用现用 `826b667d…` HAR，对应 `0ad5d6d…` 源码。正常核心的初始化与进程退出机制不纳入本轮。
- 并发和失败：生命周期锁阻止 Detach/Release 在通知中途改变窗口；只有窗口与属性均成功才保存尺寸。错误回滚与连续操作由生产方法替身测试覆盖。
- 工具链：先本地 DevEco26 预验证；最终改由 GitHub Actions 完整构建。CI 记录实际版本，不从本机记录推定远端版本。保留原运行库哈希，并校验 bridge 导入集避免 SDK 编译漂移。
- 范围：GL/SW 暂停重绘和 completed 留给 #84；FFmpeg/ohos_ijkplayer 由用户另行安排。本次 CI 只编译 bridge 和打包既有 libmpv，不构建 FFmpeg。
- 主机检查与真实设备：主机函数测试不覆盖 Vulkan 驱动或实际 swapchain；之前实验包的平板结果不能替代本 CI 包的设备验收。

不存在待用户选择的技术分歧。实际 CI 工具链及设备效果是待执行验证项，不能提前写成通过。
