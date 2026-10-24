# 接入 Player #82 门禁与长期来源的最小方案

状态：**方案待审查/实施授权，本轮不修改 workflow、脚本、SDK、远端设置或 PR 正文，不上传 SDK、不购买服务、不合并。** 保留旧锁、产品 target22/compatible15/modelVersion、八个核心库、旧候选与 TV。

## 已知基线与本次成功的边界

2026-10-25 [只读快照](evidence/ci-40110834301/pr82-baseline.json)：#82尚未合并，head为 `99b2c967675bada272bfa1c982a180ea7b2c7f66`，base main为 `951343145e076277be99f7b459ec614d5a64f8b8`，当时 test-merge SHA为 `70026ad8237cb30f1dd9184ac238a2dfd34fff5a`。这些值只用于解释当前缺口，不得硬编码为未来门禁输入。

实际 [normal-core.yml](../../.github/workflows/normal-core.yml) 已有 `pull_request`→main、若干分支push、`merge_group`和手动触发，包含宿主、旧API24/self-hosted目标及 `always()` 汇总。PR正文仍引用旧提交/缺少PR触发的旧描述，未来应随准确变更同步正文，本轮不远端改写。

**workflow中“必需”的名称不代表GitHub已强制执行。** 当前 main required-status API返回404“Branch not protected”；规则集 `19571723/main branch` 的 enforcement为disabled。因此要分别完成“工作流组合验证”和“显式启用远端规则”，不能声称正在替换已经启用的required gate。远端配置实施前重新读取。

本次 `610dd1f` 的独立push成功证明官方ARM64工具准备/目标构建可行；其源树不等于#82当时head或merge树，不能把该绿色结果移贴成#82通过。SDK26产物只用于评估，原8库固定，新增target仅ARM64。

## 最小接入路径

1. 在独立实施分支准备一个增量提交，把已审DevEco26配置与以下组合接线纳入#82拟提交树；先给精确SHA和文件范围审批，不直接修改当前远端#82。旧API24锁、门禁脚本及既有workflow历史保留。
2. 增加唯一的新结果名称，例如 `正常核心 DevEco26 组合结果`。同一事件内执行既有宿主检查和新DevEco26目标检查，汇总使用 `always()` + `needs`，只有两者真实success、证据绑定一致、收尾成功才success。missing/skipped/cancelled/failure均不通过；不能写成“旧target或新target任一成功即可”。先并行观察，不冒用旧结果名称。
3. PR路径使用 `pull_request`，默认checkout实际 `refs/pull/<n>/merge`，不强行checkout PR head。复用现有事件绑定并记录 `GITHUB_SHA`、checkout HEAD/tree、base/head SHA、父提交关系、source前后快照；base或head变化必须重新验证新merge，不能使用旧green或独立分支的推送结果顶替。
4. `push`到main或被批准集成分支时绑定实际push SHA；若启用merge queue，必须保留 `merge_group: checks_requested`，绑定实际组合SHA和base祖先。不要只依靠 `workflow_dispatch` 证明PR可合并。
5. 新profile的构建/消费入口必须明确选择 `deveco26`：沿用已核 `evaluate.py build` → 已锁Node/CLI → `build --modules vidall_player@deveco26` 的链路，不能省略模块target而回到旧default。打包/独立测试工程消费同一运行实际生成的HAR，绑定其SHA及产出步骤，禁止引用旧候选HAR或仅靠源码module依赖绕过包消费。旧default在SDK26下仍会混入新runtime并被旧门禁拒绝；旧default继续对应旧工具链，本轮不改默认目标。
6. 接入#82新profile目标门禁前，在独立consumer工程实际导入该次新HAR并完成构建，核对consumer构建日志、依赖解析、包内八库/API与HAR来源，证明入口到交付包一致；本次首跑只上传文本，尚无此consumer证据。必要HAR只在获批的同一可信任务临时目录传递，若要跨job上传HAR或签名/设备验证，另给范围预览，不自动扩大本次文本上传范围。consumer运行时/设备/发布仍独立待验。
7. 对#82当前拟合入树取得真正的PR组合运行，下载公开artifact核索引、源码/工具链/八库/API、consumer来源、清理与失败门禁。旧 `normal-core-result` 的 host+旧target 语义保持，失败/未满足如实保留；新profile成功不能把旧default或旧组合改写为通过。

GitHub对PR默认merge上下文、fork Secret和merge_group有明确语义；跳过job可能被视为success，required汇总须显式拒绝缺失依赖结果。[事件文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[required checks说明](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)。

## 下载凭据与fork信任边界

若来源需要Secret，最小做法是只让**经过审查的本仓精确提交**进入受审批的下载/构建环境；未来环境审批策略的配置另需明确授权。管理员确认待运行merge/head与批准对象一致，推新提交必须重新审批。仅配置repository Secret会让同仓workflow代码有机会读取它，不能把“不是fork”当成已审查。

fork PR不提供下载凭据：运行无Secret的宿主检查；目标状态显示待受控验证，组合结果拒绝绿色。维护者如要推进，先审查并将精确内容导入受控本仓分支/新的受控PR，重新验证对应merge树，并保留来源映射。不能把其他受控分支的成功直接当原fork PR通过。禁止用 `pull_request_target` + checkout不可信PR代码来绕过Secret边界，也不把缓存写权限或签名URL交给fork。

下载步骤只读来源、在临时目录中使用最小权限；token/URL经Secret注入不入日志、参数或artifact。Secret配置/轮换/删除与新源码SHA推送分别审批；本次临时 `DEVECO26_ARCHIVE_URL` 已删除，不自动复用为永久授权。

## GitHub强制规则的启用和回退

工作流接线与远端规则是两项变更。先取得同一实际PR merge上的新组合成功，并用失败、skip、缺证、base/head漂移、fork、merge_group负例证明不能假绿；确认新check名称和提供者唯一可识别。随后给出规则集当前值、拟启用值、影响分支和回退预览，由用户单独批准后才启用新组合为required，避免旧名称残留为永久pending。当前没有已启用required，不能描述为默认自动替换旧规则。

回退保留旧锁/旧workflow文件和来源证据：实施前记录原规则集与工作流SHA。若新工具链或来源故障，默认保持失败阻塞；如需回退，由用户批准恢复原规则配置及受审工作流提交，并报告恢复到disabled会失去远端强制保护。只有旧API24精确环境重新验证成功，才可另行选择把旧组合设required；不能静默关闭新检查或把失败标绿。

## 长期下载来源：先官方，备选受控私有缓存

| 选项 | 最小要求 | 当前结论 |
| --- | --- | --- |
| 稳定官方、精确版本的下载端点 | 厂商明确支持自动化获取；确认版本/授权条款/重定向链；锁定host/path与精确大小、ZIP和DMG hash，禁止自动追latest或降级到其他包 | 官方[下载中心](https://developer.huawei.com/consumer/cn/download/)是入口；目前只有一次短期签名链接证据，尚未证明26.0.0.851存在长期无人值守端点，保持待验 |
| 官方支持的受控签名URL续签 | 厂商提供可用且获授权的自动化签发方式；只在受控环境保存最小凭据，按精确归档hash验收，过期明确失败 | 未取得该能力与许可依据，不承诺可自动续签；手工更新只可作为显式临时运行方案 |
| 不变内容的私有归档缓存 | 先核安装包/SDK条款是否允许组织内部留存、自动化构建和选定存储位置；获得用户上传与存储授权后，才将已核官方原始完整归档放入已有私有存储，键绑定hash、禁止覆盖、只读下载、最小凭据、审计和保留/删除策略 | 当前未核完权利、未选存储、未上传、未购买，不视为已可用 |

已验证官方原ZIP：4078480294字节，SHA256 `86289edeb2e8e30eb1adf80cba0fc55f0e57cdd4f6dc4ec9c59985a0bc4b8524`；DMG：4103833155字节，SHA256 `13efc1cdeb65d217051831648f7a47b52eb84fe27edf6510e0a9f0200d7bb37c`。这两个hash来自完整官方HTTPS下载计算，不是独立厂商发布hash。来源/许可证、获取时间、工具版本和锁的对应关系必须继续保存；获得下载链接不等于获得再分发权，本文件不替厂商条款下结论。

若未来选私有缓存，它是**显式的新下载来源**：需在新受审提交中新增精确host/path allowlist，核对TLS/重定向/完整包大小/hash，不可通过放宽当前官方来源校验“顺便兼容任意镜像”。不得公开发到GitHub Release、普通artifact或仓库；不得上传签名、凭据或整个个人开发环境。普通Actions cache只能加速，可能淘汰且不提供永久可用保证，不作为长期来源；缓存命中仍验完整hash。

## 后续实施的TDD与批准顺序

先新增工作流结构/实际事件/汇总的RED：错误merge/head、旧树重用、缺失或skip目标、fork取Secret、失败后清理、来源非allowlist/错误hash/过期/缺Secret等。最小GREEN后保持原八库/API与旧锁，完成PR真实merge与（如启用）merge_group实跑并独立审artifact。来源许可/配置不明确时目标明确失败，不降级校验。

依次批准：方案与来源选择 → 精确实现SHA预览 → 必要凭据/私有存储动作 → PR组合运行证据 → 独立远端ruleset启用预览。没有本轮“CI通过即合并/开required/上传SDK”的隐含动作。
