# 规格质量检查清单：VidAll_Player HarmonyOS/OpenHarmony TV libmpv 组件库

**目的**：在进入技术规划前验证 VidAll_Player 可发布组件库规格的完整性、可验收性及宪章合规性
**创建日期**：2026-07-21
**功能**：[spec.md](../spec.md)

## 内容质量

- [x] 聚焦用户价值、兼容承诺、可发布组件和交付责任。
- [x] 以中文面向利益相关方；ArkTS/ohpm、NAPI、XComponent、EGL/GLES 与 libmpv 仅作为用户明确要求的产品边界，不规定代码结构或实现算法。
- [x] 所有必填章节均已完成。

## 需求完整性

- [ ] HAR 内部 native 打包/装入、公开 Surface 接入、SMB lease 协作、ARM64 真机与受控样本、GPL/LGPL 发布审批等关键决策已关闭；关闭前不得宣称无待澄清项。
- [x] 功能需求可测试且表述明确。
- [x] 成功标准可度量。
- [x] 成功标准不依赖具体实现方式。
- [x] 已定义全部主要验收场景。
- [x] 已识别生命周期、网络、权限、字幕、性能和发布边界情况。
- [x] 已明确首期范围、非目标和延后能力。
- [x] 已识别 VidAll_TV 兼容性、目标设备、素材、许可证、受控私有制品源和发布凭据等依赖与假设。
- [ ] HAR 内部 native packaging spike、SMB lease 确认协议、ARM64 API 22 TV 真机/样本访问和许可证/source offer 审批尚未有真实结论，必须作为实施与发布阻断项跟踪。
- [x] 首期范围已明确：外挂音频/字幕 URL 可规划，下载缓存、裁剪、去隔行和截图均为稳定 `FEATURE_UNSUPPORTED`；WebDAV 配置与目录浏览属于示例/消费者而非公开 SDK。
- [x] 公开 `eventEpoch`、Surface generation 与 SMB lease 状态事件已定义；验证构件先取证、证据齐全后才创建 candidate 的制品时序已定义。

## 功能就绪度

- [x] 每项功能需求均可映射到一个或多个验收场景、能力证据或发布审计结果。
- [x] 用户场景覆盖基础播放、WebDAV、音轨/字幕、流媒体/SMB、ArkTS/ohpm 组件安装、双渠道发布和示例生命周期。
- [x] 成功标准覆盖用户完成、稳定性、设备证据、组件消费、供应链、私有制品与 GitHub Release 一致性以及隐私结果。
- [x] 规格未把“已构建”误写为“已支持”，并要求三态能力结论。
- [x] 已符合工程宪章的中文文档、API 15/19/22、TV 焦点、生命周期、隐私和发布门禁要求。
- [x] 明确本库不得改造、构建、提交、发布或以任何形式变更 VidAll_TV；兼容性通过独立矩阵和消费方验证定义。
- [x] 组件发布门禁明确覆盖锁定依赖、SBOM、许可证、校验、API 兼容记录、敏感信息和 GitHub Release/私有制品一致性。

## 复核记录

- 第 1 次复核（2026-07-21）：既有规格无占位符、无待澄清项，已覆盖核心播放、兼容和供应链。
- 第 2 次复核（2026-07-21）：更新项目命名与受众为 VidAll_Player 组件库；补齐 ArkTS/ohpm 可安装组件、GitHub Release、批准私有制品发布、双渠道一致性、发布阻断条件和“不得改动 VidAll_TV”的验收。
- 第 3 次复核（2026-07-26）：根据当前实现的只读调研，新增真实 libmpv bridge、首帧、surface generation、release 后静默、HAR 内部 native 交付、HTTP/WebDAV 重定向与 SMB lease、独立 consumer-smoke 和 ARM64 真机门禁要求。HAR native packaging、lease 协作、真实设备/样本和许可证审批仍待关闭，因此不再宣称所有检查项通过。
