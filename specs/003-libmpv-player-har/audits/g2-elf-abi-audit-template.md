# G2 ELF/ABI 联合审计记录

> 本文件由执行审计后填充为"记录"。此记录对应 libmpv.so 原生产物；HAR 包内 `libvidall_player_native.so` 单独审计见"加载边界"节。
>
> **重大更正（2026-08-05）**：上一版记录"当前 HAR 无 libmpv.so / native bridge 未链接 mpv"是基于 **8 月 2 日过时的 `default@PackageHar` 缓存**（当时打包的是 8.6KB probe）。已执行 `devecocli build clean` 全量重建，重新打包的 HAR 已正确纳入真实播放链路（见"加载边界"节）。

- `candidateId`：`draft`（待分配；HAR 已含真实播放内核，可进入后续验证）
- `sourceCommit`：`native/config/sources.lock.json` 锁定 mpv `v0.40.0` commit `287d7cdb…`、ffmpeg `n7.1.1`、samba `4.20.7`、gnutls
- 目标 ABI：`arm64-v8a`（TV / 负责人 G1 确认中）
- 产物路径与 SHA-256：
  - `entry/src/main/cpp/third_party/libmpv/arm64-v8a/libmpv.so`（来源，not stripped，56MB）`99204080…`
  - CI/default 构建 stripped 产物（`llvm-strip --strip-all`）：`75d7240e2a15377187efd990cd5aa718c7635e3700edbca2927eb0cac6996c0d`（由当前来源 `99204080…` strip 而来，确定性可复现）
  - 重建 HAR `packages/vidall-player/build/default/outputs/default/vidall_player.har`（22.8MB）：内 `package/libs/arm64-v8a/libmpv.so` SHA `75d7240e…`（与独立构建一致）；`libvidall_player_native.so` strip 后 116KB（#58 新增 position 事件观测代码后体积由 176KB 增至此值）
  - CI HAP `entry/build/ci/outputs/default/app/entry-default.hap`（61MB）：内 `libmpv.so` SHA `75d7240e…`；native 116KB，NEEDED/UND 符号与 HAR 内一致
- 审计工具：`llvm-readelf`（DevEco NDK `/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/llvm-readelf`）

| 类别 | 记录 | 结论 |
| --- | --- | --- |
| ELF 头与 ABI | 针对 libmpv.so；`arm64-v8a`（ELF64/AArch64）目标，详情记录于 `release/audits/g2-elf-audit.json` | 已审计 |
| `NEEDED` | libmpv.so 12 个：`libc++_shared`/`native_media_vdec`/`acodec`/`codecbase`/`core`/`window`/`vulkan`/`c`/`ohaudio`/`buffer`/`image`/`EGL` | passed |
| 导出符号 | 38677 个；含 `SMBC_*`×51、`FT_*`×155 → **libsmbclient/FreeType 已静态链入 libmpv.so** | 已审计 |
| allowlist | 12 个 NEEDED 全部在 allowlist；`neededLibraries == allowedLibraries` | passed |
| denylist | 禁止 `libsmbclient.so`/`libavplayer.so` 作为动态依赖 → NEEDED 中未出现（`forbiddenNeededLibraries` 为空） | passed |
| 加载边界 | **重建后 HAR 已含完整播放链路**：`package/libs/arm64-v8a/` = `libmpv.so`(53MB) + `libvidall_player_native.so`(116KB) + `libc++_shared`；native `NEEDED` 含 `libmpv.so`，`UND mpv_*`（create/initialize/render_context_create/observe_property 等，#58 新增 time-pos/duration 观测）15 个 → bridge 真实驱动 libmpv | passed |
| 材料关联 | SBOM(SPDX-2.3+CycloneDX)、NOTICE、license-audit、来源锁已生成至 `release/`；HAR 与 HAP 内 libmpv.so SHA `75d7240e…` 与独立构建一致 → 材料与交付物对应 | 已审计（NOTICE 待法务复核） |
| 可复现性 | HAR 内 libmpv.so SHA = CI 独立构建 SHA = `75d7240e…` → `reproducible: true`（`g2-reproducible-build.json`） | passed |

**结论**：libmpv.so 的 ABI/依赖审计通过（NEEDED 全部 allowlist，denylist 未出现，可复现）；**重建 HAR 已真实纳入 libmpv.so 并由 native bridge 驱动**，加载边界与材料关联均一致。"无播放内核"的旧结论因过时缓存而废除。剩余 G2 缺口集中在真机播放证据（G1/G3）、受控源码树/构建 manifest、NOTICE/许可证法务复核及负责人签收；在全部补齐前 G2 仍为 **No-Go**，但已具备可审计的真实交付物。
