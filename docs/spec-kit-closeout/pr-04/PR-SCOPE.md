# PR4 交付范围、依赖与剩余工作

“PR1–PR4”是本次交付拆分编号，不是已经创建的GitHub PR号码。本次只准备Player文档，不创建PR，不推送、不合并。

## 四个交付单元

| 交付编号 | 仓库/端点 | 职责 | 与PR4关系 |
| --- | --- | --- | --- |
| PR1 | ohos_ijkplayer / `codex/phase17-mpv-repro`（盘点端点前缀 `67d35542`） | FFmpeg/OHCodec生产入口、构建闭包、宿主工具锁定、Spec Kit、独立HX509历史诊断及可重复构建 | 生产职责的基础；不把历史诊断生成器设为默认。 |
| PR2 | ohos_ijkplayer / `codex/phase20-runtime-directories`（盘点端点前缀 `ad0e403e`） | 精确依赖/SDK输入闭包与Samba运行目录，含phase18 | 新正常输入与运行配置依赖；约254MB输入单独披露审查。 |
| PR3 | ohos_ijkplayer / `codex/phase28-validation`（盘点端点前缀 `427148d8`，实际到Phase31） | OHCodec/HDR/释放链、normal terminal接口、设备与运行验证 | PR4接入其正常组合与公共扩展；PR3相对PR2审查，防止重复提交。 |
| PR4 | VidAll_Player / `codex/004-normal-core-integration`，精确端点 `66e9d3350bc64f41d26cb1938fa94027a1642b65` | 完整正常核心、公开初始化/terminal契约、真实异步桥接与独立HAR消费者 | 当前Player交付单元；本目录的纯文档提交以后续独立预览附加，不改已批准端点。 |

producer端点前缀用于对应2026-10-24分支盘点，不替代[输入清单与来源锁](EVIDENCE.md)。默认交付顺序为PR1→PR2→PR3→PR4，可并行草稿审查。PR1与PR2是同一master分出的两条线；路径无交集不证明合并后语义正确。PR3依赖PR2，PR4逻辑依赖producer组合完成审查；跨仓合并不会自动更新Player固定八库。

## Player PR4 包含与不包含

包含[004规格](../../../specs/004-normal-core-integration/spec.md)的八核心库/来源材料、应用私有运行目录初始化、显式受控退出策略、真实native异步工作及终局父级保护、独立HAR消费者、宿主门禁和分层证据。既有诊断及状态/Surface兼容要求保留。

不包含TV代码接入或HAR替换、原Player工作树的旧未提交内容、旧候选迁移、默认SDK升级、私有ohpm/公开发布、历史IJK/HDR开发。旧候选与默认生成器保留。TV未来接入需显式初始化和终局接管、仅应用保屏，并原子处理旧六库与完整新HAR，不能混装；应另列规格、验收和精确推送预览。

## 后续门禁：尚未实现

[normal-core.yml](../../../.github/workflows/normal-core.yml)目前仅监听 `codex/004-normal-core-integration` 的push及manual，不监听pull_request。此次 `66e9d3` 的CI成功不能自动覆盖本文档分支、未来PR head、PR merge ref或合并后的组合。

后续应在单独工程任务中补充PR事件门禁，并在producer计划组合上核对来源锁/配方入口/Python修复，再对精确新SHA运行匹配检查。该工作**尚未实现，本轮不修改workflow或脚本**。新修复/组合提交需要独立精确SHA预览和用户批准；不得把既有绿灯直接贴给新SHA。本次文档只做链接/任务集合/白名单核验，不跑构建、设备或长播。

## 保留验收与历史失败

- 低API目标安装/运行、API22原始认证要求、手机及跨设备仍按对应任务待验。
- 真实GPU调用永不返回、完整平台极端并发及物理HDR/主观声画没有因宿主测试或独立注入而关闭。
- NAS短播放成功不覆盖匿名/seek/断网/重连全矩阵；用户取消60分钟作为前置，历史长播未通过记录仍保留在producer Phase31证据链，不改写为成功。
- 完整私有源分发/回读、正式候选审批及发布仍没有授权；`formalArtifactAllowed=false`。
- 旧003有限Go保留历史效力，范围以当时设备/样本/候选为准，不迁移给004。
