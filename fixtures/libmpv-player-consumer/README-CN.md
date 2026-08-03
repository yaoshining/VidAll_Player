# libmpv Player Consumer Fixture

此目录是 `@vidall/player` 的独立本地消费者，仅用于开发期验证 HAR 根入口、NAPI 加载、会话生命周期和 XComponent Surface 生命周期。它不依赖、不修改也不替代 `VidAll_TV`。

## 本地构建

先在仓库根目录构建 HAR 和 fixture：

```sh
devecocli build --modules vidall_player libmpv_player_consumer libmpv_player_consumer@ohosTest
```

fixture 通过 `oh-package.json5` 中的本地 HAR 路径依赖 `@vidall/player`，消费者代码只能从该包根入口导入。不要改为导入 `src/internal`、NAPI、NativeWindow、EGL/GLES 或 libmpv 路径。构建会生成本地 `oh-package-lock.json5`，该解析文件不属于候选交付或发布材料。

如有可用的 ARM64 TV 模拟器，可进行开发期安装和生命周期回归：

```sh
devecocli run --module libmpv_player_consumer --device <设备序列号> --skip-build
```

模拟器结果只能证明构建、安装、根入口导入、NAPI 加载和 attach/detach 等开发期回归；不能证明真实媒体播放、首帧、渲染线程、资源释放时序、TV 支持或候选可发布。

## 能力与 No-Go

能力结论只能使用以下三态：`已构建待验证`、`已通过真机样本`、`不支持或暂缓`。当前候选保持 `已构建待验证`。

在同一 `candidateId` 尚未具备 G1（目标 ARM64 TV/API/媒体样本）、G2（libmpv 来源、GPL、ABI/ELF 和加载边界）及 G3（XComponent/Surface、线程和真实首帧）的真机证据与书面批准前：

- 不得上传 OHPM、公开发布或交付该 HAR。
- 不得声明播放、首帧、TV 支持或已完成 ijkplayer 替换。
- 不得将模拟器日志、Promise 成功、状态事件或 XComponent 创建视为播放证据。
