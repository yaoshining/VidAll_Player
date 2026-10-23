# 固定证据索引与可复核边界

索引基线为 `66e9d3350bc64f41d26cb1938fa94027a1642b65`。相对链接均指向本仓库文件；需要冻结原始内容时，以该提交的 Git blob 为准。本文只登记已有证据，没有运行产品测试、构建或设备操作。

## E01：001 原任务与验收边界

[001 spec](../../../specs/001-harmonyos-mpv-sdk/spec.md)、[001 plan](../../../specs/001-harmonyos-mpv-sdk/plan.md)、[001 tasks](../../../specs/001-harmonyos-mpv-sdk/tasks.md)。原任务中的“先写并运行失败测试”、API15/19/22、双平台目标clean、私有源安装及100次生命周期均按原文保留，不以当前目录/实现存在认定历史任务完成。

## E02：002 direct SMB

[002 spec](../../../specs/002-controlled-direct-smb/spec.md)、[002 tasks](../../../specs/002-controlled-direct-smb/tasks.md)。T006明确要求ARM64 API22、匿名/认证、首帧、seek、断网、重连及释放。004现有API24 NAS短播只对应其中一部分场景，不能代替整个门禁。

## E03：003 旧候选及有限 Go

[003 tasks](../../../specs/003-libmpv-player-har/tasks.md)、[G1–G3 负责人确认](../../../specs/003-libmpv-player-har/evidence/gate-approvals.md)、[最终就绪记录](../../../specs/003-libmpv-player-har/evidence/final-readiness-record.md)、[旧真机记录](../../../specs/003-libmpv-player-har/evidence/g1-device-run-template.md)、[旧Surface证据](../../../specs/003-libmpv-player-har/evidence/g3-surface-spike-record.md)。

这些文件记录候选 `003-libmpv-player-har` 在2026-08-07的有限 Go：华为智慧屏 MateTV Pro EDIS-790A、API24/OH6.1.1.130、4K HEVC与H.264 SD双样本、GL/ohcodec与元数据，旧 libmpv 标识前缀 `75d7240e…`。文件同时保留单设备、跨设备复现及源码/构建manifest后续归档限制；不能把其中“可受控分发”改读成新004已可正式发布。这里按原记录登记，没有重新验证全部旧审批附件。

## E04：004 当前规格、报告与职责

[004 spec](../../../specs/004-normal-core-integration/spec.md)、[plan](../../../specs/004-normal-core-integration/plan.md)、[tasks](../../../specs/004-normal-core-integration/tasks.md)、[报告](../../../specs/004-normal-core-integration/REPORT.md)、[公开契约](../../../specs/004-normal-core-integration/contracts/public-runtime.md)、[TV后续迁移约束](../../normal-core-integration.md)。

[宿主摘要](../../../specs/004-normal-core-integration/evidence/host/summary.json)、[真实父级链结果](../../../specs/004-normal-core-integration/evidence/host/parent-chain/green-final/results.json)、[source-identities](../../../specs/004-normal-core-integration/evidence/host/source-identities.json)是仓库内保存的本地证据，不能称为远端Linux结果。真实函数提取测试与平台替身/完整RenderLoop缺口在报告中分别说明。终局测试不证明真实GPU调用永久阻塞。

## E05：精确 SHA 的远端 CI

- 已推送提交：[`66e9d3350bc64f41d26cb1938fa94027a1642b65`](https://github.com/yaoshining/VidAll_Player/commit/66e9d3350bc64f41d26cb1938fa94027a1642b65)。目标分支 `codex/004-normal-core-integration`，父提交 `951343145e076277be99f7b459ec614d5a64f8b8`。
- [CI run 39981170659](https://github.com/yaoshining/VidAll_Player/actions/runs/39981170659)：事件 `push`，工作流 `.github/workflows/normal-core.yml`，head为上述完整SHA，结果 `success`。
- artifact ID `12512998256`，名称 `normal-core-host-66e9d3350bc64f41d26cb1938fa94027a1642b65`，ZIP 22,007字节，SHA256 `9e23fe55e74845016b6645e246cea65bd991f31343c70371928e0846f6fd3fcc`，下载后与GitHub digest一致。
- artifact内74个UTF-8文本文件、26,888字节；Linux x86_64，47条host checks通过（含工具和编译步骤，不等于47个测试用例）；4个源码身份与精确commit blob匹配，文本上传门禁通过。
- 同SHA内的[工作流](../../../.github/workflows/normal-core.yml)与[重放入口说明](../../../scripts/test/normal-core/README.md)提供可执行范围；本次文档收尾未运行它们。远端CI不重建producer，也不是HarmonyOS目标clean/低API真机证明。

CI链接是远端记录定位，不保证artifact永久可下载；当时工作流设定14天保留期。上述hash使后续副本可核对，不能在下载失效时声称仓库已内含原ZIP。当前仓库没有永久收录远端原artifact；本目录只保存其审查摘要。新文档SHA、未来PR head和merge组合必须另做门禁，不能借用这次绿灯。

## E06：正常输入闭包

[清单](../../../release/inputs/004-normal-core/manifest.json)、[核验结果](../../../release/inputs/004-normal-core/INPUT-VERIFICATION.json)、[输入说明](../../../release/inputs/004-normal-core/README.md)、[来源锁](../../../release/inputs/004-normal-core/provenance/source-lock.json)、[SBOM](../../../release/inputs/004-normal-core/provenance/sbom.json)、[许可证索引](../../../release/inputs/004-normal-core/licenses/index.json)、[正常组合绑定](../../../release/inputs/004-normal-core/provenance/normal-library-binding.json)、[Samba资源审计](../../../release/inputs/004-normal-core/provenance/samba-resource-audit.json)。

新libmpv为 `1a469850c99635671281ddadc3c35e65121efda3da5382745cc3c33c8ddaaa31`，完整八核心动态库与新的Player bridge形成ARM64九库。这里只说明固定输入、来源、补丁/工具链索引、许可证和资源材料，不声明正式法律审查完成或覆盖全部API设备。Python目标路径修复保留在对应producer输入中，不在本轮改写。

## E07：目标产物与短真机结果

[双clean HAR比较](../../../specs/004-normal-core-integration/evidence/dual-clean-har.json)、[原始HAR身份](../../../specs/004-normal-core-integration/evidence/normal-har-frozen.json)、[规范化消费者身份](../../../specs/004-normal-core-integration/evidence/normalized-consumer-identity.json)、[正常事件摘录](../../../specs/004-normal-core-integration/evidence/normalized-consumer-events.txt)、[设备摘要](../../../specs/004-normal-core-integration/evidence/device-verification.json)、[NAS事件摘录](../../../specs/004-normal-core-integration/evidence/consumer-smb-events-03.log.txt)、[终局退出核验](../../../specs/004-normal-core-integration/evidence/terminal-exit-verification.json)、[终局夹具身份](../../../specs/004-normal-core-integration/evidence/terminal-fixture-identity.json)、[边界核验](../../../specs/004-normal-core-integration/evidence/boundary-final.json)。

原始两次HAR整包hash不同，39文件payload相同，差异是封装mtime；规范化HAR完整SHA `e8fa9afb6c0594d44ac380eb41fe7dff48ea3bc4ba82f279c0ae2e78a4127af4`。实际消费者HAP SHA `068c6a5735b6ea7a90417ce19ce22b1c65a737faeea51adfca1ec367d595d993`，包内九库身份已对应。API24正常场景记录两次首帧、零错误、暂停/恢复、20秒关键帧seek、关闭重开和保屏释放；NAS记录Basic鉴权后短出帧与位置推进。它们不是60分钟、SMB断网重连全矩阵或API22结果。

独立terminal链接接缝记录事件、错误、保屏关闭、退出请求及进程/Ability/窗口消失；不能独立区分宿主kill与native deadline，不能冒充真实GPU故障。仓库只有脱敏P32事件摘录/身份摘要，私有原始日志未提交。失败摘录和原报告的失败说明保留，没有因后续通过而删除历史失败。

## E08：T015 事后审查摘要与本机补充

`66e9d3` 精确预览为350个变更文件，新版本blob合计59,617,757字节，含8个ELF核心库54,005,456字节及5模板PNG图标221,587字节。独立clean checkout对350文件逐字匹配、工作树干净，按锁安装TypeScript5.6.3后47条host checks通过；独立审查通过后用户授权该完整SHA推送，后续远端身份由E05核对。原始5份许可证CRLF暂存转换问题已通过仅新增输入路径的 `-text` 修复并经clean重放核验，不修改许可证原始字节。

以上是当时完成的检查摘要。原始精确预览、clean重放、CI ZIP及逐文件索引保存在本机 `/private/tmp/phase32-player-integration-20261023/preview/`、`ci/`，独立审查在 `/private/tmp/phase32-root-review/`。这些路径可能被清理，**只属于本机补充，不是仓库可复现或永久链接**。本目录不复制私有原始设备日志、凭据、签名、库或HAP。后续需要永久保存远端artifact时另行审查脱敏归档范围，不把本次文档摘要冒称原始证据全文。
