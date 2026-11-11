# 交给 ohos_ijkplayer 的说明

VidAll_Player 当前使用的 Phase30 A FFmpeg 输入中，`libavcodec/ohdec.c`（SHA-256 `d7c4bcc960d54dcae930168a56fcd6cf2b064e8758294b9e6a98c80768f19499`）在 `oh_decode_close` 中退役输出和回调、等待在途操作后调用 `OH_VideoDecoder_Stop` 和 `OH_VideoDecoder_Destroy`。任一步返回错误都会置位进程级 `ohcodec_terminal_failure`，之后 `oh_decode_create` 在调用平台创建接口之前直接返回 `AVERROR_EXTERNAL`。请分别注入 Stop 失败及 Destroy 失败，核对旧代回调、token、buffer 和 Surface 的归属，并评估在安全保留旧实例、限制保留数量的前提下，能否让同一 PID 中的新实例用新 Surface 恢复硬解。验收时请提供新旧实例标识、各阶段平台返回值、下一部片的画面及音频输出。VidAll_Player 的平板复现注入的是 Vulkan 关闭等待错误，没有观察到 FFmpeg Stop/Destroy 失败。

## 2026-11-11 上游处理与消费接入

上文是原始问题交接，已由 [ohos_ijkplayer PR #11](https://github.com/yaoshining/ohos_ijkplayer/pull/11) 修复并合入 `master` 的 `32887363cb103163fe6557ca64c05539ad6d73f2`。本轮授权消费其已交付 SDK，六库已更新到恢复版。上游正常 SDK 是本地构建，Player HAR 仍由 iMac CI 构建；来源及 ABI 核验见 `release/inputs/004-normal-core/provenance/ffmpeg-recovery-compatibility.json`。

Stop/Destroy 返回错误时以旧实例隔离，Destroy 成功才释放 Surface 占用，失败保留原 Surface 并允许新 ID 创建。上游 API 24 平板的两项返回错误与正常六库验收仅证明上游记录中的组合；本轮 Player 新组合仍需单独设备验证。永久挂起和 FFmpeg 保留资源耗尽未被上游验收。
