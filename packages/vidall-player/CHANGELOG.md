# 变更日志

本文记录 `@vidall/player` 的重要变更。

## 未发布

### 变更

- 将目标分发许可调整为 `GPL-3.0-or-later`，以匹配包含 libmpv 和静态 Samba SMB 路径的分发义务。
- 明确播放器仅以 libmpv 为目标内核，不使用 HarmonyOS AVPlayer。
- 暂停 OHPM 上传；当前包仅供 VidAll_TV 集成验证，待真实 libmpv bridge、设备验证和发布门禁完成后再决定发布。
- 将公开 API 限定为已文档化的播放器契约；其余 mpv 能力须经实现和验证后再公开。

## [0.1.0] - 2026-08-02

### 新增

- 面向 HarmonyOS TV 和手机应用的初始 ArkTS HAR 候选包。
- 公开 `createPlayer` 工厂，以及 `VidAllPlayer` 生命周期、播放、轨道、字幕、事件和错误 API。
- Surface 生命周期 API，以及本地文件、HTTP(S)、HLS 和 DASH 输入路径校验。
- 中英文使用文档、GPL-3.0-or-later 许可证文本和 OHPM 包元数据。

### 已知限制

- 当前 HAR 未接入真实 libmpv 播放 bridge，也未携带可分发的 libmpv 运行时，不能用于真实播放。
- 设备相关编解码器、协议、硬解和性能行为仍需在目标设备验证。
- `smb`、缓存请求、裁剪、去隔行和截图均不属于稳定支持能力。
