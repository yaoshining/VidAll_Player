# 远端配置模板与分阶段批准

**本文件是未执行模板，不是远端写入授权。** 当前只有本地实现；不新建Environment、不设置变量/Secret、不启用规则、不合并。执行前刷新实际仓库状态，预览必须给出具体值，不能以占位符获得授权。

## 先推精确代码，再确定实际PR合并提交

#82当前head为99b2c967675bada272bfa1c982a180ea7b2c7f66，目标分支codex/docs-pr4-speckit-closeout。本轮最终预览应同时列出相对该head的全部累计差异（含610dd1f和6741c4a祖先）与相对6741c4a的本轮增量。获批后仅非force更新该分支，不合并。

新workflow的push白名单是main和codex/deveco26-pr82-gates，不包含#82分支；#82更新由pull_request事件运行，默认checkout refs/pull/82/merge。代码推送后才只读取得新head/base/实际merge SHA；`DEVECO26_APPROVED_EVENT_SHA` 必须等于当次 **merge SHA**，不能填head或猜测未来merge。审批前target可能skip，组合结果明确失败，这是缺少授权而非已验证成功。待精确配置获批后，针对同一事件重新运行；base/head再变化必须重新取merge并审批。

## 配置审批内容

| 项目 | 拟采用模板 | 必须确认的实际值/边界 |
| --- | --- | --- |
| 仓库变量 | DEVECO26_APPROVED_EVENT_SHA | 推送后读到的40位实际PR merge SHA；无值/旧值拒绝target，merge_group也须精确事件SHA |
| 新环境 | deveco26-build | 当前只读查询没有该环境；不得修改现有copilot环境。名字存在不能当保护已生效 |
| 环境Secret | DEVECO26_ARCHIVE_URL | 仅放新环境，不放repo级；新的受支持官方精确归档链接，过期/缺失失败；通过stdin写入，不输出query；验证结束删除。原临时Secret已删、原链接已过期，均不复用 |
| reviewer | 用户确认的GitHub审查者 | 单用户场景可提出yaoshining作为reviewer、prevent_self_review=false的可执行方案；同一账户触发时true会自锁，不能默认要求不可执行保护。若有第二审查者再提true方案；用户单独批准 |
| 防绕过/平台支持 | 若账户和仓库支持，禁用管理员绕过 | 必须读取实际保护与支持情况，不能仅凭模板认定平台支持 |
| 部署ref策略 | selected/custom policy | 第一轮仅允许实际PR事件ref refs/pull/82/merge；不凭head分支名批准PR。push/main与merge_group运行另提供具体事件ref和匹配策略；不预先放行所有分支 |

GitHub部署策略使用事件ref语义，通配符`*`不跨`/`。当前main没有启用保护，不能选择“仅protected branches”然后假定它限制到main；没有受保护分支时该策略可能允许所有分支。配置后必须API回读required reviewer、prevent_self_review、绕过选项和实际branch policy，并用允许/拒绝事件验证。[官方环境文档](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)。

fork绝不取得Secret：无凭据host可以运行，target因非fork条件拒绝，always汇总不得绿色。即使同仓代码也必须经精确SHA和Environment审查；禁止pull_request_target检出不可信PR后读取凭据。配置变量与environment/Secret之前，先审查该精确代码，不能把“同仓”当信任来源。

## GitHub强制门禁另行启用

当前规则集disabled，workflow名称含“必需”不等于GitHub已强制。先取得新组合对实际PR merge的真实成功及公开artifact独立回读，再给具体规则差异预览，另批准是否启用 `正常核心 DevEco26 组合结果` 为required。保留旧normal-core.yml和旧锁，旧结果如实显示；不做旧或新任一成功的OR。

失败默认阻塞。若要回退，先预览具体工作流/规则回退；恢复disabled会失去强制保护，必须明确报告并批准。只有旧API24精确环境重新通过，才可考虑另批准旧组合required。consumer真机/发布仍待验。
