# 首轮云端原生契约失败返修

## 真实结果

42d79a3395235fc848d4b9a0816aef65e21e5f72已获批准推送，#82正文按精确预览更新。对应merge34f8002b1cb153e950b06339b8aded7397100387：默认云端工作流40133260897的宿主检查通过，target因仍绑定旧审批SHA而跳过，组合失败；诊断宿主40133260855通过。原生来源工作流40133260852在controlled-release.test.sh旧交叉构建job断言失败，这是实际契约遗漏，不是目标审批导致。

本地完整原生11脚本复核为9过2失败：除上述controlled-release外，git-mirrors.test.py仍从活动workflow解析已退役job，后续将发生IndexError。上轮仅运行新流程/版本门禁未覆盖这两处旧断言，既有失败记录保留。

## 最小修复与TDD

- controlled-release完整历史构建、工具、闭包与许可证断言继续逐项执行，但读取已归档的原精确workflow；Git镜像测试仍由真实Git解析URL，读取同一历史配方，不访问LAN。
- 新活动workflow解析测试固定历史配方SHA，校验producer必经、全部11脚本、双平台needs/matrix、SBOM/许可证/NOTICE及上传失败条件。
- 先保留真实CI RED，并新增活动必经语义RED；复审追加comment/echo/`|| true`负例后失败复现，再使用实际非注释命令行及完整命令模板核验；再补set +e、shell/defaults覆盖、前置exit和heredoc负例，以有限已审完整run白名单拒绝未使用的控制流覆盖。缺失/跳过/忽略失败/平台缩水/排除平台/上传缺失或warn/篡改归档均拒绝。
- 原生任务显式准备官方Node22，使用仓库既有锁定yaml2.8.1依赖的npm ci；不依赖开发机碰巧存在node_modules/PyYAML，不新增依赖版本。

最终精确源码需重放活动workflow实际完整11脚本、新解析器与变异、元数据生成命令、相关工作流/组合测试和actionlint。此次不修改SDK、目标构建helper或产品源码，无需再次4GB准备/HAR/Hypium重建；42d79的目标证据只绑定其原SHA，不能冒充返修提交重新构建。

新提交推送与新实际merge授权仍需精确批准。本轮不改变量/Secret/环境/runner/ruleset，不合并、不替换候选，不改TV；旧批准正文保持原字节，新正文如需更新另出预览。
