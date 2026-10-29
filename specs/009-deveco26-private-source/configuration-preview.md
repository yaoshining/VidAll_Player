# 后续只读配置预览（本轮不执行）

代码先以精确 SHA 更新 Player #82 的现有 `codex/docs-pr4-speckit-closeout` 分支；获得批准并推送后，再只读取得 GitHub 实际生成的 PR merge SHA。当前旧 merge `b6543c6e72f20c3a263021c2901f19aa3009b24f` 不授权新代码，不能预填成未来批准值。本文件仅明确配置范围，不授权不确定 SHA 或凭据。

## 最小配置

- Player 仓库保持 public；缓存 `yaoshining/vidall-toolchain-cache` 保持 private。
- 新建 Player 环境 `deveco26-build`。required reviewer 为 `yaoshining`（id `4533657`），`can_admins_bypass=false`、`prevent_self_review=false`：目前仅本人触发和审批，防自审开启会造成自锁。允许本人审批不等于自动批准运行。
- 环境使用 custom deployment branch policy，仅允许 `refs/pull/82/merge`。它按实际 `GITHUB_REF` 匹配，不是 PR head 分支名；main、其他 PR、merge_group 的放行以后另批。
- 新建 **仓库级**变量 `DEVECO26_APPROVED_EVENT_SHA`，值必须是批准后的当次实际 merge SHA。job `if` 在进入环境前求值，放入环境级变量会导致该门禁不可用。base 或 head 变化需重新审批新的实际 merge SHA。
- 仅该环境新增 `DEVECO26_RELEASE_READ_TOKEN`。用户创建 fine-grained PAT，仅选择缓存单仓库，`Contents: read`（附带 GitHub 必需的 Metadata read），不授予写入/其他仓库权限。上传者既有写权限不交给 CI。token 不发聊天、不放文件/日志/提交，不由本轮工具生成或读取。
- 成功 GET/下载只证明读取能力，不能证明 token 没有写权限。只读属性依据用户创建时权限配置及可用的权限元数据回读；不执行写入试探。
- 2026-10-25 的认证只读盘点确认环境与同名仓库变量不存在；实际配置前仍须重新核对，有冲突即停止，不覆盖。配置完成须回读 reviewer、禁止管理员绕过、精确 ref policy、变量值及 Secret 名称元数据，不能仅凭环境名存在就宣称保护生效。

PAT 到期/轮换由用户确定并在实际配置审批中写明；不把长期下载来源理解为无限期 token。该 Secret 限受审 target 的 bootstrap step；host 无凭据，后续 SDK/CLI/consumer 子进程移除下载 token。原 GITHUB_TOKEN 保持 contents:read 且不能默认跨仓读取私有缓存。

## 推送后的执行与回退

先批准精确代码推送；默认缺变量时 target 跳过、组合汇总明确失败。读取新 merge SHA 后，再给具体配置动作及凭据期限审批。环境需要人工批准；一次实际 CI 必须核 run/head/merge、私有来源证明、HAR/consumer、cleanup 和下载 artifact，缺一步继续待验。默认分支 ruleset/required check、本轮 PR 正文、旧 normal-core 工作流均不改。

撤销仓库批准变量使后续 target fail-closed；撤销环境 Secret 并由用户吊销 PAT。保留失败与来源证据，不改旧工具链锁或改用未批准源。是否启用为分支保护必需检查，是后续独立授权。

参考：[GitHub 环境及部署规则](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)、[Release asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset)、[runner 网络域](https://docs.github.com/en/actions/reference/runners/larger-runners)。
