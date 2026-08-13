# libmpv 受控发布流程

## External FFmpeg staging

`native/scripts/build-libmpv-bootstrap.sh` 不再构建或静态链接 FFmpeg。构建前必须设置：

```bash
export OHOS_NDK=<OpenHarmony NDK 根目录>
export VIDALL_PLAYER_FFMPEG_PREFIX=<ohos_ijkplayer FFmpeg 8 ARM64 shared prefix>
native/scripts/build-libmpv-bootstrap.sh
```

prefix 约定如下：

- `include/libav*`：FFmpeg 8 public headers。
- `lib/libav*.so*`、`lib/libsw*.so*`：包含 unversioned linker name、SONAME link 和完整版本文件。
- `lib/pkgconfig/*.pc`：`libavcodec`、`libavformat`、`libavutil`、`libavfilter`、`libswresample`、`libswscale`；bootstrap staging 时重写 `prefix=`。
- `VERSION`、`configure-options.txt`、`MANIFEST.tsv`、`ELF-REPORT.txt`：不可变来源、ABI、配置和 ELF 证明。
- `licenses/GPL-3.0-or-later.txt`、`licenses/FFmpeg-LGPL-2.1-or-later.txt`：发布许可证文本。

输入必须是 FFmpeg 8.0、ARM64、`--disable-static --enable-shared`，并保持既有播放能力：`libsmbclient` 及私有凭据补丁、network、dav1d、mbedTLS、libxml2/DASH、ohcodec、PNG/MJPEG encoder。任何 `libav*.a` 都会被拒绝。producer 的 Samba/GnuTLS 闭包静态进入 `libavformat.so.62`；不得动态依赖 `libsmbclient.so`。

## 运行时所有权

bootstrap 将运行时输入输出到 `dist/ffmpeg-runtime/arm64-v8a`，但不把它复制到 HAR。最终宿主 HAP 必须在同一 ABI 目录统一打包：

- `libavcodec.so.62`
- `libavformat.so.62`
- `libavutil.so.60`
- `libavfilter.so.11`
- `libswresample.so.6`
- `libswscale.so.9`

HAR 只能携带 SDK 自身 native bridge，禁止携带上述 FFmpeg 副本，避免多个 HAR 重复打包或加载不同实现。

## ELF、ABI 与体积审计

构建后 bootstrap 使用 `${OHOS_NDK}/llvm/bin/llvm-readelf` 和 `llvm-nm`（兼容 NDK 的 `native/llvm/bin` 布局）生成 `dist/libmpv/arm64-v8a/elf-audit.json`。门禁要求：

- `DT_NEEDED` 完整包含上述 6 个版本化 FFmpeg SONAME。
- 不出现 `libsmbclient.so`，不导出或内嵌完整 `avcodec`/`avformat` 实现符号。
- 默认 `libmpv.so` 上限 25 MB，可通过 `VIDALL_PLAYER_LIBMPV_MAX_BYTES` 收紧；FFmpeg runtime 单独记录体积。
- ARM64、MPV/NAPI/ArkTS public API 与宿主播放回归必须保持不变。

## 许可证与发布

MPV 为 GPL-2.0-or-later；启用 Samba `libsmbclient` 后 external FFmpeg runtime 按 GPLv3 审核。最终 HAP 发布必须同时提供 MPV、FFmpeg、Samba 及静态传递闭包的许可证、NOTICE、精确源码、producer 构建脚本和源码提供说明。`VERSION` 中的凭据 patch 必须能由 `MANIFEST.tsv` 追溯；缺少来源证明时不得发布。

受控制品仍通过 `native/scripts/build-libmpv-controlled.sh` 生成 SHA-256、feature manifest、SPDX/CycloneDX SBOM、NOTICE、许可证与 ELF 报告；候选版本还需通过 ARM64 TV 能力证据和双构建可重复性验证。
