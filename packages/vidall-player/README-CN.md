# VidAll Player SDK

`@vidall/player` 是面向 HarmonyOS 的 ArkTS 播放器候选 HAR。播放器唯一的播放内核是 libmpv，不使用 HarmonyOS `AVPlayer`。包的唯一公开入口是 `Index.ets`；只应导入本文列出的 API。

## 候选状态

该包尚未发布到 OHPM，只能由本仓库的独立 fixture 用于开发期验证；不修改或依赖 VidAll_TV。HAR 包含内部 NAPI 和 ARM64 libmpv 候选产物，但 G1（目标设备/样本）、G2（供应链）和 G3（Surface/线程）尚未关闭。构建、模拟器安装、会话创建或 XComponent attach/detach 成功都不能视为媒体播放、首帧、TV 支持或可发布能力。

公开 API 暂严格限定为本文所列契约。未在本文声明的 mpv 命令、属性、脚本、滤镜、录制、流捕获和截图均不是公开 API，并返回 `FEATURE_UNSUPPORTED` 或其他类型化错误。

## 本地 fixture

当前不提供 OHPM 安装、上传或公开发布方式。仅可由本仓库的 `fixtures/libmpv-player-consumer/` 通过本地 HAR 路径依赖进行开发期验证：

```sh
devecocli build --modules vidall_player libmpv_player_consumer libmpv_player_consumer@ohosTest
```

fixture 只能从 `@vidall/player` 根入口导入；不要导入 `src/internal`、NAPI、NativeWindow、EGL/GLES 或 libmpv 相关路径，它们不属于兼容性承诺。

## 开发期接口

`createPlayer()`、`attachSurface()`、`resizeSurface()`、`detachSurface()`、`load()`、`play()`、`stop()` 和 `release()` 是候选接口。调用成功、生命周期事件或模拟器日志只证明受控桥接路径执行，不构成媒体播放或首帧结论。页面销毁时仍应调用 `release()`；释放后的实例不可复用，应重新调用 `createPlayer()`。

未批准的能力会返回类型化错误。例如，`requestCache()` 返回 `FEATURE_UNSUPPORTED`；无有效 Surface 的 `load()` 返回 `SURFACE_UNAVAILABLE`；释放后控制调用返回 `RELEASED`。公开错误经过脱敏，不能依赖其包含完整 URI、原生句柄或加载路径。

## 能力状态与门禁

能力只能标为 `已构建待验证`、`已通过真机样本` 或 `不支持或暂缓`。当前候选是 `已构建待验证`。

ARM64 TV 模拟器仅用于构建、安装、根入口导入、NAPI 加载和生命周期回归。它不能关闭以下门禁：

- G1：目标 ARM64 TV/API、媒体样本闭集和复现规则。
- G2：libmpv 来源、GPL 材料、加载边界、ABI/ELF 和候选准入。
- G3：XComponent/Surface、NativeWindow、线程、输入和真实首帧。

在同一 `candidateId` 的真机证据和 G1/G2/G3 书面批准完成前，不得交付 HAR、上传 OHPM、公开发布，或声明播放、首帧、TV 支持及 ijkplayer 已被替换。

## 许可

候选 libmpv 分发物包含 GPL 组件，SMB 路径涉及 Samba。任何后续受控分发必须依照 [GNU General Public License v3.0 or later](LICENSE) 并完成 `docs/controlled-libmpv-release.md` 规定的材料和审批；当前状态不构成分发授权。
