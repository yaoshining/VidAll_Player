# 一致性审查

A1 对应 layout、完整输入身份校验及生产分片验证；A2 对应独占目录、部分写入清理、路径/symlink/重复覆盖负例；A3 对应确定性 manifest、无 URL query/本地路径断言；A4 对应可信锁、缺片/错序/重复/篡改/替换过程中一致性测试；A5 对应独立全量资产复算与精确预览。

原 006/007 文档和已封存证据不改。原 archive-lock 的 `persistentSourceVerified=false` 保留，指官方长期源未验证；未来私有 Release 验证应在独立来源结果记录，不能改称官方永久 URL 已验证。这个离线工具不包含未来包装器或 GitHub token 处理。

Spec Kit 按 specify→plan→tasks→implement，根审查已通过规格/计划与代码复审；前置检查返回当前008目录。最终精确本地提交的 clean 测试、提交文件计数与独立审查在外部预览记录，防止冻结提交提前声称其自身重放完成。
