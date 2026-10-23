# 一致性分析（实施前）

FR01/12 对应 T001/T013–16；FR02–03 对应 T004–07；FR04–08 对应 T008–10；FR09–10 对应 T004–05；FR11 对应 T011–13。来源、运行时、终局、独立消费者均有独立测试任务；产品实现尚未开始，未将计划写成完成结果。

审查已固定：initializePlayerRuntime/onPlayerTerminal/getPlayerRuntimeStatus；terminalPolicy 显式 controlled-app-exit；deadlineMs 整数1000–10000，fixture3000，无默认值；每订阅者一次及迟订阅回放；诊断明确缓存标记。采用显式受控退出策略是用户已批准的方向，无需再次询问该方向。API低版本硬加载风险需先证据核对，发现不一致立即报告。

## 实施后核对

FR01–12 保持原范围。T004–T013 的来源输入、47 条宿主门禁、目标双 clean、独立 HAR 消费和短真机结果见 REPORT.md 与 evidence；T014 历史保护基线复核通过。原 Player/TV 的 HEAD、分支、tracked status、index 均匹配，12 个保护产物及 7 个保留文件匹配；producer index 既有 stat 差异保留说明。T015 的精确提交重放和独立审查结果放提交外 preview，避免提交自引用；T016 新远端 CI 待精确 SHA 批准后执行。未验收项没有改写通过。
