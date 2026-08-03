# G2 候选材料清单

每项必须关联同一 `candidateId`；任何未完成项均阻断准入。

- [ ] `libmpv.so` 来源定位、不可变版本和摘要
- [ ] 精确对应源码定位与摘要
- [ ] GPL-3.0-or-later 原文许可证
- [ ] NOTICE
- [ ] 来源锁
- [ ] 可执行构建脚本与工具链说明
- [ ] 构建 manifest
- [ ] SPDX 或 CycloneDX SBOM
- [ ] 两次独立构建的产物 SHA-256 摘要与比较结果
- [ ] 目标 ABI 审计
- [ ] ELF `NEEDED`、导出符号和动态依赖 allowlist/denylist 审计
- [ ] HAR/私有原生层加载位置、顺序和失败语义审计
- [ ] 同一候选的目标真机首帧、播放、失败和释放证据
- [ ] G1、G2、G3 负责人书面 Go 确认

当前候选：`draft`；G2 结论：No-Go。
