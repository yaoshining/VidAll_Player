# 一致性与范围审查

先完成Spec007/plan/tasks及prerequisites，审查后TDD实施。旧SDK锁、原normal-core.yml、006/005封存、产品API/model/signing和八库均未改。

初始计划复用旧libmpv-player-consumer，审查指出它没有initializePlayerRuntime/onPlayerTerminal，新契约在该真实源文件上失败；改为只读复用normal-core-consumer/entry/src/main，并在临时工程生成API22/min15、无签名构建配置，不修改原fixture。新增实际临时HAR缺API编译负例证明编译器确实消费包的公共声明，正常路径则通过。

旧汇总仅有host+旧target，与新增consumer要求不同，保留旧函数不改；新profile增加显式三方结果、负例、cleanup、事件/source身份。新workflow target先匹配非fork与精确已批准事件SHA，再进入受审环境；名字存在本身不是保护证据。所有远端动作仍需具体预览。

root已审并独立检查正常HAR/HAP、具体ArkTS负例和保护边界。最终推送预览以#82真实head99b为比较基线列出累计差异，同时列本轮6741以来增量，保留610dd/6741提交链。最终head不是PR merge；推送后再取实际merge给变量配置审批，不提前猜值。
