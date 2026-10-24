# 本地验证与待验范围

## 本轮已证明

真实 RED 分别覆盖旧组合缺来源证据仍可通过、新工作流没有私有下载入口、实际传输函数不支持合法 302、HTTPError 承载重定向、错误 tag ref、合法无 Content-Length 元数据被拒、finish 借用缺失/旧来源证明、注入模拟传输误作 CI 证明。依赖未安装导致的 MODULE_NOT_FOUND 不计语义 RED。

下载器 18 组测试验证实际 request header、固定 API/CDN、200/302、HTTPError、401/403/404/500、尺寸/逐片/完整哈希、manifest/资产身份、磁盘、独占目录、故障清理、子环境、stale bootstrap 结果和模拟证明拒绝。gates 8 组、workflow 21 个拒绝变异覆盖新来源必需性及 Secret 范围；原 consumer 9 组保持通过。旧 bootstrap 回归和 actionlint 另有真实执行记录。机器摘要及原始日志 SHA 见 [evidence/local-tests.json](evidence/local-tests.json)。

失败输出曾含测试断言的宿主环境 repr，已删除该原始输出，仅保留其摘要/删除记录及清空宿主环境后的脱敏语义 RED；不纳入提交或归档。其他失败记录保留。

## 精确提交后的必要集成

冻结后只进行一次 clean 源码重放。原已核 4,078,480,294 字节 ZIP 为模拟 HTTP 的分片体，执行真实流式回拼、每片及完整 SHA 验证，再调用未修改的 bootstrap prepare --archive 准备真实 SDK/CLI，最后真实 cleanup。复用同源 npm 缓存仍经 npm ci 和工具闭包校验；不将其描述为冷缓存网络验证。

集成程序 `release-source.integration.py` 不使用私有 token、不联网下载 4GB、不构建播放器。结果必须明确 `networkMode=local-original-archive-backed-mock`、`privatePATVerified=false`、`actualTargetBuildPerformed=false`、`remoteCISourceProofAllowed=false`。子环境只记录检查的键和移除布尔；清理结果记录实际退出码。精确提交身份及真实集成最终结果随提交外预览提供，避免 self-referential commit。

## 继续待验

- 新 readonly PAT 对私有 Release 的实际云端下载、权限配置及受保护环境审批。
- 新 merge SHA 的目标 HAR/consumer 组合 CI。既有 007 构建证据不冒充本轮新 CI。
- 新组合真实磁盘峰值；起始 17,629,502,863 字节门槛是旧保守预检加 2 GiB 余量，不是实测峰值保证。
- 产品运行时与未完成真机项目；本轮不重跑长播，不替换候选。

旧官方 archive-lock 的 persistentSourceVerified=false 保留；已发布的私有 immutable Release 是独立内部 CI 来源，不证明官方永久 URL 或整个归档再分发许可范围。旧 SDK/归档锁、API、八库与 TV 保持原内容。
