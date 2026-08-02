# VidAll Player SDK（候选）

`@vidall/player` `0.1.0` 是 HarmonyOS TV/手机播放器 SDK 的候选 HAR。`Index.ets` 是唯一公开入口；消费者只能使用 `createPlayer` 和公开类型，禁止导入 `src/internal`、NAPI、NativeWindow、EGL/GLES 或 libmpv 句柄。

## 能力状态

能力均采用三态：`已通过真机样本`、`已构建待验证`、`不支持或暂缓`。候选目前未完成 ARM64 API 22 TV 的 100 次生命周期、媒体样本和受控 consumer 验证，因此不得将任何构建结果视作发布支持。

- 支持的候选接口：surface 生命周期、HTTP(S)/HLS/DASH 输入校验、轨道与字幕选择、结构化事件和释放。
- 运行期参数：视频/音频参数、解码器和硬解状态仅报告真实观察；SDR 是默认基线，HDR 不作承诺。
- 稳定不支持：缓存请求、裁剪、去隔行和截图返回 `FEATURE_UNSUPPORTED`。
- 直接 `smb://`：不支持或暂缓；不得在 URI 中携带凭据。

详细候选门禁见 `release/capabilities/arm64-tv-evidence.json`、`release/capabilities/arm64-tv-media-matrix.json` 和 `scripts/evidence/ijk-compatibility-matrix.json`。
