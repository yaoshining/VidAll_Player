# Player 与 TV 的恢复接口职责

状态：实现及宿主验证中；新接口尚未随完整 CI HAR 交付。消费端跟进 [VidAll_TV #372](https://github.com/yaoshining/vidall-tv/issues/372)，关联 #370，独立于 #371。

## 播放方式

`PlayerOptions.playbackMode?: 'standard' | 'compatible'`：缺省为 standard，保留原来的零拷贝硬解选择。compatible 强制软件解码和软件渲染，不初始化 Vulkan/EGL、OHCodec interop，也不申请硬解隔离名额。该选项优先于 hardwareDecoding；原 hardwareDecoding=disabled 仅禁用解码器，保留现有渲染选择，不改变旧调用语义。

兼容模式只有在 preserve-host 策略且 recovery.state=ready 时允许在终局后新建；故障前创建的兼容实例同样属于旧代，不能直接复用。无软件渲染能力或配置失败时必须返回失败，不悄悄回退 GPU。纯软件渲染仍涉及 NativeWindow/PixelMap，不等于与系统图形服务完全隔离。

## 故障与媒体关联（实现及端到端验证中）

普通媒体错误沿用 Player 的 error 事件；OHCodec 故障新增 `onPlayerFault` 订阅和 `getPlayerRuntimeStatus().faults` 有界历史。`PlayerFaultInfo.kind` 为 session-quarantined 或 process-terminal，含 sequence、stage、platformError 及 attribution。attribution.state=known 时 sessionId/loadGeneration 都是十进制字符串；unknown 不携带确定身份。历史最多 16 条，监听者按 sequence 去重，注册时重放现存历史，返回函数用于取消订阅。监听独立于单个 Player 生命周期，关闭期间的故障仍能记录。

mpv 的加载扩展把身份绑在命令及 playlist entry，解码器在创建时捕获，随后由帧携带；OHCodec 故障只采用 last_src 的身份。候选新帧、当前页面、当前加载代、Surface generation、owner_tag 均不能补猜旧资源的来源。创建回滚 LATE 无可靠已使用帧时为 unknown。整个路径不记录媒体 URL。

**尚未完成接入闭环**：加载开始前向 TV 提供不可变身份回执，及解码/过滤/映射整条链的目标运行验证仍待完成；不得把目前的数值故障记录按当前页面强行映射到媒体。T013 保持未完成。恢复 ABI 已升为 0x00020000，新增加载与故障快照接口；ABI 版本或必需符号缺失会拒绝 preserve-host，不能静默改成退出宿主。

TV 维护稳定媒体身份和有界标记存储。Player 不持久化视频黑名单。仅实际关联相关故障的视频记兼容选择；本进程临时被迫兼容的其他视频不记失败。进程重新启动后全局临时限制自然结束，不复位旧进程的终局锁。

## 全局故障恢复（设备待验证）

初始化显式传入 `{ terminalPolicy: 'preserve-host', deadlineMs: 3000 }`。运行库必须提供恢复 ABI，否则返回 RUNTIME_RECOVERY_UNAVAILABLE，不能自动降为 controlled-app-exit。后者只用于原有调用兼容，不是 TV 新接入建议。

进程状态永久保持 terminal；另有 recovery.state：pending 表示等待旧音频停止，timeout 表示超过观察期限但仍保留资源，ready 表示旧音频已静止且允许新代兼容会话。deadlineMs 在 preserve-host 下只是状态观察期限，不结束进程、不清除硬解锁。宿主查询可见 timeout 后变为 ready。

ready 后销毁/放弃旧 Player，对新 Player 显式指定 playbackMode=compatible。代际由 Player 捕获，宿主不伪造或更新实例代。旧实例操作仍返回 PLAYER_TERMINAL；ready 前新兼容创建返回 PLAYER_RECOVERY_PENDING。标准硬解创建始终被拒绝。新兼容实例正常释放可以归还名额。

旧 GPU/解码资源不强行释放。旧音频和焦点必须停止影响新播放，旧回调代关闭，待完成请求有界返回；旧线程和保留对象必须受总预算约束。只有验证这些条件后才能开放不退出宿主的新初始化策略。错误切换最多自动尝试一次；新播放应有画面及独立音频，兼容失败允许返回列表。达到上限不能靠无限保留或移除保护来满足续播。

TV 负责提示与导航，只有收到切换成功后才显示“已切换兼容模式”。自动恢复不能解除用户暂停或尚未结束的音频打断。
