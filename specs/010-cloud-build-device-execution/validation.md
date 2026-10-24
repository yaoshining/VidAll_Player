# 本地验证与未完成范围

## 已有证据

- 第一轮真实RED：原活动工作流仍有4条self-hosted任务；原状态脚本在构建失败情况下仍按签名存在报告built=true；原consumer staging不含Hypium。
- 新汇总RED：缺Hypium证明仍可成功，回归后拒绝。实际SDK拒绝临时ohosTest→product映射，先补禁止映射回归，再仅修临时staging。
- 检查点ec7c473：原14项CTest+2项诊断JS与完整47项正常核心宿主矩阵通过；固定producer交付与完整输入审计组合独立审查通过，包含真实许可证/头文件/资源变异拒绝。
- 首次HAR实际成功；修正staging后官方OhosTestCompileArkTS及PackageHap完成，实际entry_test unsigned HAP含565668字节ABC，九库与当次HAR相同、产品API22/15未变。首个配置拒绝日志原样保留；此探索结果不是最终冻结源码重放。
- C控制器22项合成制品/真实文件锁测试通过。全部为宿主契约，不是实际签名、验签或设备执行。
- actionlint检查实际全部工作流及真实上下文负例；最终精确提交重放结果由外部只读证据索引绑定，不回写冻结提交形成循环。

## 发现的既有不一致

原894f0feb的签名validator与原profile配对仍报“模块vidall_player未应用到环境ci”：它逐target要求全部product，deveco26实验目标只用于default。失败早于本轮修改的workflow断言。原产品配置、签名材料和validator均未改，失败单列，不声称所有签名配置测试通过。本轮unsigned工程不依赖该历史签名路线。

## 仍待验收

- 新精确提交推送及实际云端运行，须新的mergeSHA授权；当前环境审批变量只覆盖旧提交。
- producer最新normal完整组合目标云端重建；当前只消费固定既有八库。
- 含合成媒体的设备包与专用bundle、正式受控签名及verify-app、HDC执行适配器、实际设备短场景/离线/保屏清理。
- iMac专用label/控制器部署，main工作流生效顺序与正式required规则选择；本轮未改远端设置。
- 原Hypium九套运行契约适配、物理HDR和主观声画。本轮不重跑长播、不更换候选、不修改TV。
