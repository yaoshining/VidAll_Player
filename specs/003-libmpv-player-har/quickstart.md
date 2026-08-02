# 快速验证指南

## 验证目的

本指南用于验证计划、研究工件和未来受控候选的 No-Go/Go 边界，不提供实现代码。当前三个决策门禁未关闭，执行结果应为“研究记录完成、真实功能准入被阻断”，不能报告播放成功。

## 前置条件

- 当前仓库位于 `003-libmpv-player-har` 分支，且只允许修改 `specs/003-libmpv-player-har/`。
- 已准备负责人书面确认模板、目标真机访问条件和脱敏日志存储位置；未确认时不得自行选择支持设备或媒体。
- 未来自动化构建使用项目标准 HarmonyOS 工具链；构建命令应优先使用 `devecocli build`。本计划阶段不运行构建、不生成 HAR 或原生产物。
- 独立 consumer fixture 只能在本仓库创建；不得修改、构建或引用 VidAll_TV。

## 当前 No-Go 验证

1. 阅读 `research.md`，确认三个决策均为未关闭，且每项有负责人确认项和停止条件。
2. 阅读 `contracts/player-contract.md`，确认所有 ArkTS/NAPI/渲染接口都标记“暂定/待证实”，没有 AVPlayer 或回退路径。
3. 阅读 `contracts/controlled-delivery-contract.md`，确认候选准入要求同时包含许可证、NOTICE、精确对应源码、构建脚本、SBOM、ELF/ABI、加载审计和真机证据。
4. 阅读 `data-model.md`，确认能力三态与 `candidateId`、设备、样本和审批引用关联；`已构建待验证` 未被描述为支持。
5. 预期结果：当前候选保持 `blocked` 或 `draft`；不得出现“已支持”“真实首帧已通过”或可供消费者使用的声明。

## 门禁关闭后的最小验证顺序

以下步骤只能在负责人分别关闭三个门禁后执行：

1. **准入审计**：对同一 `candidateId` 执行来源、许可证、NOTICE、精确对应源码、构建脚本、SBOM、ELF/ABI、加载边界和可复现性检查。任一失败即拒绝候选。详见 `contracts/controlled-delivery-contract.md`。
2. **自动化 TDD**：先写 ArkTS/NAPI 契约测试，再实现最小变更；每项能力至少覆盖成功、无有效画面/无效输入、快速重复停止/释放、释放后调用和陈旧 generation 回调。测试不得把内存状态机或 probe 当作真实播放断言。
3. **独立 fixture**：在本仓库 fixture 中通过受控本地路径安装 HAR，执行公开导入与创建；不得访问内部模块或 VidAll_TV。
4. **真机 spike**：在负责人确认的 ARM64 TV/API 及批准媒体样本上记录 attach、resize、detach、重建、load、首帧、播放、失败、stop、release 和重复 release；采集视频/截图、脱敏日志、事件序列、设备/API、候选与样本摘要。
5. **结论归档**：把结果写入能力证据，按三态更新。只有所有材料、真机记录和审批引用齐备，最小已验证子集才可标记为 `已通过真机样本`。

## 预期结果与失败处理

- 缺少负责人确认：停止在 No-Go，补充决策材料，不创建真实功能任务。
- 缺少受控材料或 ELF/ABI/GPL 审计：拒绝候选，不交付 HAR。
- 没有 NativeWindow/EGL/GLES 真路径首帧：保持“已构建待验证”或“不支持或暂缓”。
- fixture 必须修改 VidAll_TV 才能工作：停止；重设 fixture 边界。
- 任一 AVPlayer 使用或回退：立即失败，禁止替代实现。
