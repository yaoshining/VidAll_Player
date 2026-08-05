# G2 候选材料清单

每项必须关联同一 `candidateId`；任何未完成项均阻断准入。

- [x] `libmpv.so` 来源定位、不可变版本和摘要（`sources.lock.json` mpv v0.40.0 `287d7cdb…`; SHA 见 ELF 记录）
- [ ] 精确对应源码定位与摘要（mpv 源树已定位，但受控源码目录尚未就位）
- [x] GPL-3.0-or-later / GPL-2.0 / LGPL-2.1 原文许可证（`release/licenses/` license-audit；samba GPL-3.0 需法务）
- [x] NOTICE（`release/licenses/NOTICE`）
- [x] 来源锁（`native/config/sources.lock.json`）
- [x] 可执行构建脚本与工具链说明（`native/scripts/*`）
- [ ] 构建 manifest（受控构建 `build-libmpv-controlled.sh` 需受控源码目录 + PKG_CONFIG_LIBDIR 才能生成）
- [x] SPDX 或 CycloneDX SBOM（`release/sbom/sbom.spdx.json` + `sbom.cdx.json`）
- [x] 两次独立构建的产物 SHA-256 摘要与比较结果（`release/audits/g2-reproducible-build.json`: `reproducible: true`，双 SHA `75d7240e…`；须补真正独立二次构建）
- [x] 目标 ABI 审计（arm64-v8a；`g2-elf-audit.json` status passed）
- [x] ELF `NEEDED`、导出符号和动态依赖 allowlist/denylist 审计（`g2-elf-audit.json` passed；denylist libsmbclient/libavplayer 未作动态依赖）
- [x] HAR/私有原生层加载位置、顺序和失败语义审计（**重建后 HAR 已含 libmpv.so + native bridge(NEEDED libmpv.so, UND mpv_* 14个)**；待补真机加载记录）
- [ ] 同一候选的目标真机首帧、播放、失败和释放证据（G1/G3，需真机）
- [ ] G1、G2、G3 负责人书面 Go 确认

当前候选：`draft`；G2 结论：**No-Go**（ELF/依赖审计通过、HAR 已含真实 libmpv 播放内核且可复现；剩余受控源码树、构建 manifest、真机证据与负责人确认未补齐）。
