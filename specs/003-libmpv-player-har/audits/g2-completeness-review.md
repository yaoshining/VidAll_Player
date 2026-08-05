# G2 审计完整性审查

- 更新日期：2026-08-05T02:13:09+08:00
- 审查对象：G2 模板、比较记录与已生成的审计材料；实际执行 ELF/ABI、可复现构建、SBOM/NOTICE 审计，并实测解包 HAR。

| 强制材料或规则 | 当前状态 | 结论 |
| --- | --- | --- |
| GPL 许可证、NOTICE、来源锁 | `release/licenses/` NOTICE + license-audit（GPL-2.0/GPL-3.0/LGPL-2.1，samba 待法务）；`sources.lock.json` 在库 | 已生成 |
| 精确对应源码、来源锁与摘要 | 来源锁存在；受控源码目录 / 构建 manifest 未就位 | 部分缺失 |
| 构建脚本与双次构建 | `native/scripts/*`；`g2-reproducible-build.json` `reproducible: true`（双 SHA `75d7240e…`） | 已验证（须补独立二次构建） |
| SBOM | `release/sbom/sbom.spdx.json`（25 包）+ `sbom.cdx.json` | 已生成 |
| 目标 ABI、ELF `NEEDED`、符号和依赖规则 | `release/audits/g2-elf-audit.json` passed：12 NEEDED 全 allowlist，denylist 未出现，38677 符号 | 已审计 |
| 加载位置、顺序和失败语义 | **HAR 曾因过时缓存未含 libmpv.so；clean 重建后已纳入 libmpv.so(53MB)+native(176KB)，native NEEDED libmpv.so、UND mpv_* 14个** → 真实播放内核就位 | 已修复，待真机记录 |
| 真机能力证据 | 未提供（G1/G3，真机未握手） | 缺失 |
| 三门禁负责人确认 | 未提供 | 缺失 |

结论：libmpv.so 的 ELF/ABI 依赖审计通过且**支持 rebuild 的证据**——此前判定"HAR 无 libmpv.so/无真实播放内核"源于 8 月 2 日过时 PackageHar 缓存，`devecocli build clean` 重建后 HAR/HAP 均正确携带 libmpv.so，native bridge 真实链接 mpv，SHA-256 跨 HAR/HAP/独立构建一致（`75d7240e…`），可复现成立。剩余缺口为真机证据、受控源码树、构建 manifest、NOTICE 法务复核与三门禁负责人确认；补齐前门禁仍 No-Go。
