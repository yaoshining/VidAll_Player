# Spec018 任务

- [x] T001 从最新main创建codex/x86_64-har；只读核验依赖。证据evidence.json；Todoist `6j2gC295FrP57H3G`。
- [ ] T002 取得并核验完整上游x86_64 SDK。r2 已取得，309 项摘要/六库架构/依赖通过；**阻塞于缺少 SMB 宿主运行时接口**，见 sdk-acceptance.md 及[上游Issue #12](https://github.com/yaoshining/ohos_ijkplayer/issues/12)；Todoist `6j2gC2F2HCqQW28G`。部分完成，不勾选。
- [ ] T003 先红后绿补Player多ABI核心、NAPI及HAR构建/审计，保留ARM64及Spec017。Todoist `6j2gC2FR9ChrRGjp`。
  - [x] T003a SDK 宿主运行时前置门禁：9 项单元测试先红后绿；真实 r2 正确拒绝，最小链接复现缺符号。仅完成门禁，不代表多 ABI 核心实现；Todoist `6j2h5Q8mfc68rwvp` 已完成。
- [ ] T004 iMac CI、独立消费、x86_64模拟器验证，交付原始HAR与哈希。Todoist `6j2gC2GjwFQf4v9p`。

分组`Spec018 · x86_64 HAR交付`，section `6j2g9x5HHGRfcVwp`；复用原x86总任务`6j2g2Cx8C3QRMQvp`，自Spec017迁入，未完成。没有新的x86 HAR地址，不在后台自动等待或触发上游构建。

负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)；thread ID `01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`；host `local`；更新2026-11-16。
