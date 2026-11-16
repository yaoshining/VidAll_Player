# Spec018 任务

- [x] T001 从最新main创建codex/x86_64-har；只读核验依赖。证据evidence.json；Todoist `6j2gC295FrP57H3G`。
- [x] T002 取得并核验上游 r3 x86_64 SDK：332 项摘要、六库架构/依赖、配套 SMB 头文件/动态导出及实际消费者链接通过；证据 r3-sdk-evidence.json、r3-link-probe.json。仅输入验收，不代表运行验收；Todoist `6j2gC2F2HCqQW28G`。
- [x] T003 先红后绿补Player多ABI核心、NAPI及HAR构建/审计，保留ARM64及Spec017。证据 implementation-evidence.md、host-regression.json、本地双架构 HAR/消费者。Todoist `6j2gC2FR9ChrRGjp`。
  - [x] T003a SDK 宿主运行时前置门禁：9 项单元测试先红后绿；真实 r2 正确拒绝，最小链接复现缺符号。仅完成门禁，不代表多 ABI 核心实现；Todoist `6j2h5Q8mfc68rwvp` 已完成。
- [ ] T004 iMac CI、独立消费、x86_64模拟器验证，交付原始HAR与哈希。Todoist `6j2gC2GjwFQf4v9p`。

- [x] T004a iMac CI 原始 HAR、独立消费者及 Hypium 编译通过，原包和18库核验完成。见 delivery.md、ci-delivery.json；Todoist `6j2q9jhRPR4WJvRp`。
- [ ] T004b x86_64 模拟器运行：iMac 无实例/镜像，正常音画、暂停恢复、seek、关闭重开、坏片续播未验收。Todoist `6j2q9jp4qjfq86Gp`。

分组`Spec018 · x86_64 HAR交付`，section `6j2g9x5HHGRfcVwp`；复用原x86总任务`6j2g2Cx8C3QRMQvp`，自Spec017迁入，未完成。CI HAR 地址已记录于 delivery.md；未触发上游构建，运行验收缺口保持未完成。

负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)；thread ID `01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`；host `local`；更新2026-11-16。
