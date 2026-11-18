# Spec 019 · API 19 TV 旋转视频首帧

[Player #95](https://github.com/yaoshining/VidAll_Player/issues/95) · [TV #372](https://github.com/yaoshining/vidall-tv/issues/372)

## 用户场景与验收

- 从 HarmonyOS 5.1.1（API 19）ARM64 TV 模拟器的正式文件源入口以 MPV standard 模式播放同一音视频流的 0°、90°、180° MP4 对照。90° 样片被 mpv 解析为 270°。
- 三个角度均须首帧方向正确、后续画面变化、原进程持续存活。直接调用 libmpv 软件渲染 API 的回归额外覆盖另一侧四分之一转和缺失目标参数。
- 同仓 iMac GitHub Actions 构建完整 ARM64 HAR 并验证独立消费者。记录源提交、运行编号和下载原件 SHA-256。TV #372 原样接入该 HAR 并记录模拟器复测。
- 保持公开 API、播放器模式和输入依赖。实际 TV 硬解属于独立验收证据。
