# 后续远端变更预览范围（当前不执行）

1. **精确代码推送**：复用当前分支生成最终SHA，审查相对当前PR82 head894f0feb的全部diff，非force更新既有PR分支。原894f批准不覆盖新SHA。代码冻结/本地重放/清理完成后才生成真实文件数/bytes，不预填未来SHA。
2. **云端构建授权**：推送后只读取新PR merge；更新repo级DEVECO26_APPROVED_EVENT_SHA到该精确值需独立明确批准，不沿用f28aa；环境只准refs/pull/82/merge、reviewer及现有只读SDK来源权限保持。main/merge_group若正式启用需另列精确ref policy和授权机制，不以“默认CI”静默扩大私有Secret可见范围。
3. **旧门禁退役/required选择**：只在职责映射、新全量云端检查完成后，给出旧/新check名称、旧工作流触发差异、ruleset/branch protection真实状态与回退方案。新增required配置单独批准，不假设当前已强制启用。
4. **iMac标签/执行环境**：现runner21作为设备专用；拟新增vidall-device-imac并移除通用构建deveco标签的准确前后集合/所有受影响调度须预览。新device环境、手动触发默认分支限制、reviewer、具体设备并发组、读取artifact权限以及控制器固定SHA须逐项批准。当前不注册/改label、不改runner服务PATH或SDK。
5. **签名与首次设备会话**：专用bundle、证书/profile设备授权、工具SHA和安全取密位置由用户确认；不生成/搬迁私钥到云端。签名输入由已审run/attempt/artifactID/ZIP/HAP/媒体摘要组成精确会话预览。首次安装/测试/删除目标bundle/本次资源与保留期获批后才执行。

现有private SDK Secret仅用于已审云端下载；不复制到iMac设备工作流。当前iMac读取设备列表不构成签名或安装授权；本轮只准备缺配置拒绝、来源核验和无凭据控制器测试。

执行顺序限制：PR82尚未合并时main旧workflow仍会派发self-hosted，不能先移除deveco标签。只有云端路线已在main生效、旧运行已结束且同一窗口获批才切换。harmonyos-test现有自定义标签保留，其他消费另行核对。新增workflow_dispatch未进入默认分支前不承诺UI可触发。当前classic main保护404；ruleset19571723存在但disabled，未来required是新增启用，不是替换已生效强制检查。
