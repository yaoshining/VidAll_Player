# 状态与证据模型

- 尺寸请求：会话 handle、Surface generation、width、height；必须属于当前未释放且就绪会话，尺寸均大于零。
- 通知事务：原尺寸 → 窗口调整 → mpv 属性通知 → 提交新尺寸。任一步失败返回错误；属性失败尝试回滚原尺寸；回滚失败标记 renderer 不可用。未新增公开状态。
- CI 产物身份：repository、sourceCommit、runId、runAttempt、runURL、harSHA256、harBytes、库列表、实际 toolchain。
- 库约束：HAR 恰有原五个共享库成员；libmpv/两个 runtime 哈希固定；两个 bridge 可重编译，但导入及依赖集合固定。
- 验收记录：绑定 CI 产物哈希、平台、操作步骤、观察、日志/图像引用、通过项和未完成项。禁止将主机、模拟器、云平板与 TV 结果混为一项。
