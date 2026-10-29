# 本地验证与验收范围

## 检查点53e413c

这是本轮实施检查点，不是最终发布SHA；[持久摘要](evidence/checkpoint-53e413c.json)保存产物/依赖/清理/测试及原始证据摘要。其真实本地流程使用显式已核archive与同源npm缓存：准备、实际SDK CMake回归、显式deveco26 target单次clean/HAR、临时HAR公共API缺失编译负例、独立normal consumer unsigned HAP、两类consumer daemon与目标SDK清理均通过。所有子命令实际退出码保留，local模拟的事件/审批变量不代表远端Environment已配置。

- 新组合契约6项、consumer契约9项、workflow结构15项变异通过；真实旧verdict无consumer仍通过和旧fixture缺初始化API的RED分别保留为新能力缺口/fixture选择错误，不改写旧门禁语义。
- 临时HAR仅删除package/Index.d.ets中的initializePlayerRuntime导出；正常同一fixture的ArkTS编译明确报该成员缺失，不能用下载/工具链/任意失败代替。原target HAR和八库未修改。
- 正常consumer只消费entry/libs/current.har；实际OHPM锁指向该文件，展开九库与声明hash对应当次HAR，HAP九库逐字节一致，SDK26 compile、target60002022/min50003015保持。
- 宿主47项全部通过；锁定actionlint及作用域负例通过。最终精确提交将再次进行必要源码绑定重放，不把此检查点结果冒称最终SHA结果。
- 根独立直接解包HAR/HAP核验9库与API通过；12项保护产物、7项旧封存和原主仓binary diff均保持。

## 待验

新workflow尚未推送/运行，#82实际merge尚未应用本轮代码；远端变量、Environment reviewer/ref保护及Secret均未配置，required ruleset未启用。步骤见[配置模板](remote-configuration.md)。长期来源[仍有明确缺口](source-plan.md)。

consumer已构建不等于已运行；没有签名/安装/低API真机/HDR/主观声画或发布验收。未改变旧候选、产品API、八库或TV。formalArtifactAllowed=false。
