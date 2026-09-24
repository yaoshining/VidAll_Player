# libmpv 受控发布流程

## External FFmpeg staging

`native/scripts/build-libmpv-bootstrap.sh` 不再构建或静态链接 FFmpeg。构建前必须设置：

```bash
export OHOS_NDK=<OpenHarmony NDK 根目录>
export VIDALL_PLAYER_FFMPEG_PREFIX=<含 OHCodec 的 FFmpeg 8 ARM64 shared prefix>
native/scripts/build-libmpv-bootstrap.sh
```

CI 默认从固定提交构建 FFmpeg 与 OHCodec 补丁，并调用仓库已有 SMB/GnuTLS 静态闭包脚本；不再下载已过期的 `31637632656` Actions artifact。每次 workflow attempt 使用独立临时目录，源码获取后校验完整 commit。Samba、FFmpeg 和补丁仓库均通过 `fetch-locked-source.py` 浅获取固定提交（不拉取完整历史或 tag）：Samba 单次 900 秒，其他仓库单次 300 秒，最多 3 次，连续 30 秒低于 1 KiB/s 会失败；超时终止该次 Git 子进程组。每次下载尝试使用独立临时目录，失败后丢弃锁文件与不完整 pack；完整提交通过 SHA 校验后才写入目标目录。源码准备步骤另设 60 分钟总上限，避免下载异常长期占用 runner。

`build-ohcodec-ffmpeg.sh` 构建后调用 `finalize-ohcodec-prefix.py`，从实际 configure 输出与 ELF 生成下述元数据，并验证 HTTPS/TLS/SMB/OHCodec 开关及 AArch64 架构；动态 SMB/TLS 依赖会导致失败。FFmpeg 来源和补丁仍锁定为 `140fd653aed8cad774f991ba083e2d01e86420c7`、`1bab837e662ffa47ce51efd0720d3ed7c4988944`。SMB 及其依赖沿用仓库既有构建脚本，未把本次修改视为全依赖供应链审计。

prefix 约定如下：

- `include/libav*`：FFmpeg 8 public headers。
- `lib/libav*.so*`、`lib/libsw*.so*`：包含 unversioned linker name、SONAME link 和完整版本文件。
- `lib/pkgconfig/*.pc`：`libavcodec`、`libavformat`、`libavutil`、`libavfilter`、`libswresample`、`libswscale`；bootstrap staging 时重写 `prefix=`。
- `VERSION`、`configure-options.txt`、`MANIFEST.tsv`、`ELF-REPORT.txt`：不可变来源、ABI、配置和 ELF 证明。
- `licenses/GPL-3.0-or-later.txt`、`licenses/FFmpeg-LGPL-2.1-or-later.txt`：发布许可证文本。

输入必须是 FFmpeg 8.0、ARM64、`--disable-static --enable-shared`，保留 `libsmbclient` 及私有凭据补丁、network、GnuTLS HTTPS/TLS 和 OHCodec。不得将本构建未启用的外部 dav1d、mbedTLS、libxml2/DASH 声称为已具备能力。任何 `libav*.a` 都会被拒绝。producer 的 Samba/GnuTLS 闭包静态进入 `libavformat.so.62`；不得动态依赖 `libsmbclient.so`。

## 运行时所有权

bootstrap 将运行时输入输出到 `dist/ffmpeg-runtime/arm64-v8a`，但不把它复制到 HAR。最终宿主 HAP 必须在同一 ABI 目录统一打包：

- `libavcodec.so.62`
- `libavformat.so.62`
- `libavutil.so.60`
- `libavfilter.so.11`
- `libswresample.so.6`
- `libswscale.so.9`

HAR 只能携带 SDK 自身 native bridge，禁止携带上述 FFmpeg 副本，避免多个 HAR 重复打包或加载不同实现。

## HDR tone mapping 配置（issue #66）

`@vidall/player` 的 libmpv 桥接在 `mpv_initialize` 之前显式下发两个 HDR 选项，使 HDR10(PQ)/HLG/BT.2020 内容在目标电视上确定性 tone map 到 SDR，作为 VidAll_TV「AVPlayer 原生 HDR 渲染不可用」时的兜底路径：

- `tone-mapping`：缺省 `bt.2390`（渲染 API 后端 `vo_gpu` 确定性支持，mpv `auto` 对 HDR 也解析到该曲线）。
- `hdr-compute-peak`：缺省 `auto`（从 `sig-peak` 动态计算输入峰值，设备不支持 compute 时优雅降级）。

消费方通过 `PlayerOptions.hdrToneMapping`（`auto`/`bt.2390`/`mobius`/`reinhard`/`hable`/`gamma`/`linear`/`clip`）与 `PlayerOptions.hdrComputePeak`（`auto`/`enabled`/`disabled`）覆盖缺省值。注意：`target-colorspace-hint` 是 `vo_gpu_next` 专属选项，本渲染路径（`vo_gpu`）不使用；软件渲染（SW/模拟器）路径无 GL shader，不提供 tone mapping，HDR 表现仅承诺于真机 GL 路径。

HDR 能力在 `release/capabilities/arm64-tv-capability-evidence.json` 中仍为「已构建待验证」；须以 EDIS-790A 真机样本（`御赐小仵作第二季/01.mp4` HDR 黑屏样本 vs SDR 样本）验证后再升级为「已支持」。

## Dolby Vision Profile 5 色彩还原（issue #69）

Dolby Vision **Profile 5（IPTPQc2）** 片源（如 `xxx.2160p.WEB-DL.DoVi.H.265.mp4`，其 `dvBlSignalCompatibilityId=0`，无 HDR10/SDR 兼容基层）依赖 **libdovi** 才能在 libmpv 中正确还原色彩。libmpv 的 Dolby Vision RPU→RGB 处理由 **libplacebo** 承担，而 libplacebo 需同时开启两个 meson feature：

- `-Ddovi=enabled`：FFmpeg `AVDOVIData` side data 到 libplacebo 的映射（`pl_map_avdovi_metadata`）。
- `-Dlibdovi=enabled`：`libdovi` 的 RPU→HDR 元数据转换。该转换由 `pl_hdr_metadata_from_dovi_rpu` 实现，并被 `PL_HAVE_LIBDOVI` 门控——Profile 5 必须定义此宏才能把 ICtCp 正确重建为可显示色彩。

本仓库在锁定构建补丁 `native/patches/libmpv-ohos-build/0007-libplacebo-enable-libdovi.patch` 中显式补上 `-Dlibdovi=enabled`，使 `libdovi` 依赖成为确定性必选（`dovi_tools` 即 `libdovi-3.3.0` 已在 `native/config/sources.lock.json` 锁定）。注意 mpv 自身并无 `libdovi` meson 选项，Dolby Vision 还原仅经由 libplacebo 生效；`-Ddovi=enabled` 会通过 `.require(dovi.allowed())` 将 libdovi 视为必选，但显式 `-Dlibdovi=enabled` 让该承诺不被上游缺省值意外拖回 `auto`。

Dolby Vision 能力在 `release/capabilities/arm64-tv-capability-evidence.json` 中为「已构建待验证」。Profile 5（IPTPQc2，`dvBlSignalCompatibilityId=0`）须以 DoVi Profile 5 真机样本（对比 SDR 参考画面）验证后升级为「已支持」；Profile 8 须用独立 DoVi Profile 8 样本验收，Profile 5 样本只证明 Profile 5，不得作为 Profile 8 依据。AVPlayer 原生路径无法处理 IPTPQc2，故该能力仅经 libmpv 软解/渲染路径承诺。

## ELF、ABI 与体积审计

CI 受控工具链固定为 Rust `1.85.1` 与 `cargo-c 0.10.13+cargo-0.88.0`。`cargo install` 使用精确版本要求并在安装后核验完整版本，避免 SemVer 解析漂移到要求更高 Rust 版本的 `cargo-c`。

构建后 bootstrap 使用 `${OHOS_NDK}/llvm/bin/llvm-readelf` 和 `llvm-nm`（兼容 NDK 的 `native/llvm/bin` 布局）生成 `dist/libmpv/arm64-v8a/elf-audit.json`。门禁要求：

- `DT_NEEDED` 完整包含上述 6 个版本化 FFmpeg SONAME。
- 不出现 `libsmbclient.so`，不导出或内嵌完整 `avcodec`/`avformat` 实现符号。
- 默认 `libmpv.so` 上限 25 MB，可通过 `VIDALL_PLAYER_LIBMPV_MAX_BYTES` 收紧；FFmpeg runtime 单独记录体积。
- ARM64、MPV/NAPI/ArkTS public API 与宿主播放回归必须保持不变。

## 许可证与发布

MPV 为 GPL-2.0-or-later；启用 Samba `libsmbclient` 后 external FFmpeg runtime 按 GPLv3 审核。最终 HAP 发布必须同时提供 MPV、FFmpeg、Samba 及静态传递闭包的许可证、NOTICE、精确源码、producer 构建脚本和源码提供说明。`VERSION` 中的凭据 patch 必须能由 `MANIFEST.tsv` 追溯；缺少来源证明时不得发布。

受控制品仍通过 `native/scripts/build-libmpv-controlled.sh` 生成 SHA-256、feature manifest、SPDX/CycloneDX SBOM、NOTICE、许可证与 ELF 报告；候选版本还需通过 ARM64 TV 能力证据和双构建可重复性验证。

### iMac CI 的局域网源码镜像

原生交叉构建作业通过 `GIT_CONFIG_COUNT` / `url.*.insteadOf` 将 Samba、FFmpeg（含 `code.ffmpeg.org` 入口）、`libmpv-ohos-build` 和 `ErBWs/mpv` 映射到 `http://192.168.3.59:27134/yao/` 下的同名 Gitea 仓库。映射仅对子作业进程生效，不写入 runner 的全局 Git 配置。来源锁继续保留上游地址与固定提交；镜像必须包含对应提交。其他仓库和发布压缩包下载保持现有来源。此作业要求 runner 可以访问该局域网地址。
