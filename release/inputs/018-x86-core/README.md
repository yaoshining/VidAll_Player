# Spec018：x86_64 软件播放核心

本目录是 Player 编译/打包的固定输入，不是独立 HAR，也不代表目标运行验收。
ARM64 继续使用 `004-normal-core` 的既有八库；此处八库加 CI 从当前源码编译的 NAPI 桥组成 x86_64 九库。

## 来源与能力

- FFmpeg：上游 r3 SDK，源提交 `bd161c09fa66146b955d54833c0d41fb96460bdc`。SDK 下载及摘要见 `source-lock.json` 与 Spec018 的 `r3-sdk-evidence.json`。
- mpv/libplacebo：从 Spec017 封存源码输入中逐文件校验后构建；保留音频、终局通知、会话身份与宿主恢复实现。仅应用 `0016-optional-ohcodec-software-build.patch` 分离硬解编译边界。
- 构建机器：本地 macOS arm64，DevEco Native API26；构建命令、工具摘要和配置见 `provenance/`。最终 HAR 另由 iMac GitHub Actions 编译 ArkTS/NAPI 并打包。
- x86_64 软件解码、软件呈现，真实 OHAudio 输出。没有 OHCodec/Vulkan 零拷贝；不宣称 ARM64 硬件 HDR/Dolby Vision 呈现能力或相同性能。
- 字幕由 libass 使用宿主提供的字体；不依赖设备 fontconfig，未启用 PNG/WOFF2 字体功能。依赖版本固定在 `source-lock.json`，与 ARM64 的预编译依赖分别记录。
- `symbols/libmpv.so` 是未剥离符号的伴随文件；所有分配到运行内存的段内容必须与实际库对应。HAR 使用预先执行 `llvm-strip --strip-all` 的库，确保 Hvigor 再剥离后仍保持锁定字节。

## 对应源码、许可证与复建

`player-sources.tar.gz` 包含完整 mpv/libplacebo 源码及 FreeType、HarfBuzz、FriBidi、libass、Lua 官方源码归档，包括各自许可证；`source-files.json` 锁定每文件摘要。mpv 按 GPL 构建，libplacebo/FriBidi 等保留其原许可。使用这些原生库的发布方应履行相应许可证义务。

FFmpeg 及静态依赖的对应源码由上游发布：
https://github.com/yaoshining/ohos_ijkplayer/releases/download/ffmpeg8-x86_64-smb-runtime-20261116/ffmpeg8-ohos-x86_64-20261116-r3-sources.tar.gz

其 SHA-256 为 `c6ba20f67584bab8956d415c40fdfff1f1f2f89a03df7f3b5fc755dea41de0cb`。Player 不修改、构建或重新发布 FFmpeg SDK。

在仓库根目录执行，输出目录必须不存在：

```sh
python3 native/scripts/build-x86-core.py \
  --out /tmp/player-x86-fresh \
  --ffmpeg-sdk /path/to/ffmpeg8-ohos-x86_64-20261116-r3 \
  --sdk /path/to/openharmony/native \
  --meson /path/to/meson --ninja /path/to/ninja --pkg-config /path/to/pkg-config
python3 scripts/audit/x86-core-verify.py
```

复建成功不自动覆盖固定输入；重新接收产物时须绑定来源、符号文件、库摘要并运行门禁。源码归档、SDK、补丁摘要不符即拒绝。重建只消费预编译 FFmpeg，不执行其构建。

## 验收边界

本地构建、iMac HAR、独立消费构建、x86_64 模拟器和 API19 TV 真机分层记录。API19 TV 仍是独立缺口，x86 软件路径及任何 API24 结果均不能替代。
