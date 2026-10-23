# 任务：当前正常核心 PR CI

- [x] T001 只读核对workflow、AGENTS/宪章、当前库绑定及旧source-lock构建边界，形成spec/plan。
- [x] T002（FR01/05/06）先写workflow/真实git event身份与最终聚合回归，冻结基线RED。
- [x] T003（FR03/04/06）先写实际target runner的缺输入/工具/非零/timeout/错HAR及失败日志回归，冻结RED。
- [x] T004（FR01/05）最小实现事件身份helper及PR/main/merge_group触发、默认merge checkout和skip拒绝聚合。
- [x] T005（FR03/04/06）最小实现当前固定八库unsigned HAR runner、工具链身份及严格包内核验，不改产品/旧源码构建job。
- [x] T006（FR02/06）接入完整host checks、新契约测试与always证据收集，验证失败/变异被拒绝，更新执行说明。
- [ ] T007（FR07）运行Spec Kit一致性审查、全回归与一次真实目标HAR；保留失败及平台限制，不设备/长播。
- [ ] T008（FR07）本地精确提交、clean checkout重放、固定库/旧内容边界核对，提供新SHA预览；未批准不push。
- [ ] T009（FR07）用户批准后核对PR merge/新head远端CI与artifact身份；远端未运行保持待验。

T007 的 Spec Kit/host 部分已完成；目标HAR及T008精确重放在本候选冻结后记录于外部预览，不能提前勾选。T009严格等待精确SHA授权后的实际远端结果。

- [x] T010（FR08）保留真实GitHub失败、实际actionlint RED，修复job.env作用域并加入全workflow解析/归档和scope负例，缺证拒绝；原T009仍未通过。
- [ ] T011（FR08）冻结返修精确SHA并clean重放，另行取得推送批准后核对新远端CI。
