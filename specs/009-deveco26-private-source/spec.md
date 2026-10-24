# 009：私有 Release 接入 DevEco26 组合门禁

复用现有 codex/008-deveco26-release-assets 分支与 checkout；本阶段仅本地实现、验证及精确预览，不 push、不配置凭据/环境/变量/ruleset、不触发 CI。旧归档锁/SDK锁、官方 URL allowlist、API、八库、TV/候选、006–008封存不改。

## 验收

- R1 新独立来源锁绑定 private repo1432495522、immutable Release422920456、tag及metadata6a237314、三资产ID/name/bytes/digest和manifestSHA；原 ZIP 大小/完整 SHA仍由旧锁独立约束。
- R2 固定 api.github.com 元数据/资产入口，200/302严格处理；授权仅发API主机，跨主机重定向剥离凭据/cookie，只接受经官方核对的精确HTTPS资产域。拒其他协议/主机/缺证/错误状态/超长与中断，不将临时签名URL或原始异常写公开日志。
- R3 两片顺序串流到本次独占目录.partial，逐片与整体摘要通过才原子改名；失败只清理本次所有的输入文件/目录，不覆盖既有数据。起始空闲至少15,482,019,215字节加明确构建余量，不放宽旧bootstrap预检。
- R4 包装器调用原bootstrap prepare --archive，子环境移除下载token；finally删除自有ZIP并保留真实退出/清理证据。旧bootstrap和SDK cleanup不变。新组合必须核来源结果/source身份/清理成功，不允许跳过冒绿。
- R5 #82目标job改为私有来源；host仍无凭据，精确实际merge SHA及非fork/environment门禁不变，consumer真实HAR/九库/API不弱化。旧官方独立评估workflow不变。
- R6 本地网络模拟+真实文件TDD、复用原ZIP做集成，不新下载4GB、不重跑播放器构建/长播/真机。精确本地提交、至多一次必要clean重放及回收；未来推送与只读配置预览分列。

原官方persistentSourceVerified=false保持。私有托管可用、只读CI权限、运行时/许可范围验收是不同结论；远端实际只读token与组合CI继续待验。
