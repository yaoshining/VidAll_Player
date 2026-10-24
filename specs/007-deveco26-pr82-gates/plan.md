# 计划与审查门

先测试表达缺少HAR消费/错误输入/漏库/API漂移/清理错project、旧汇总不满足新组合、fork与精确事件批准等RED，再实现最小GREEN。复用006 evaluator/bootstrap工具链与旧fixture源码，新增007专属consumer/组合门禁脚本及新workflow，旧006文件和旧normal-core工作流不改。

consumer在CI_OUT/consumer/project生成独立unsigned工程，复用fixtures/normal-core-consumer/entry/src/main（含initializePlayerRuntime/onPlayerTerminal新根API）；依赖改为当次输入HAR文件，根model6.0.2、target22/min15，显式entry build。HAR/HAP仅同job临时存放。真实解析锁/展开依赖内容和打包库必须与当次HAR绑定；先clean，再构建，结束停独立home/project daemon，然后外层卸载SDK。

新组合工作流使用PR/main、push main/本集成分支、merge_group。host无Secret；target+consumer同job需要精确事件SHA变量和deveco26-build受审批环境；汇总always检查host成功及target、consumer、cleanup全部成功、身份一致。实际远端环境reviewer/防自审/允许分支配置须后续单独批准和回读。

本地按deveco-cli技能：只读官方归档、锁定Node/CLI/SDK，独立目录真实目标和consumer构建，前后源码/八库保护。先完成本地再给精确commit预览，不因长期源未闭环改allowlist或上传SDK。
