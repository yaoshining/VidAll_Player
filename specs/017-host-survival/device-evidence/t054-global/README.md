# T054 全局恢复：API24设备证据

1.0.63/API24 Mini，PID12090前后一致。诊断HAR为T053本地完整HAR，生产修复基线c7d56ee；九库不变，不是正式CI交付。1.0.62先完成流程，但导出被布局遮挡且第三会话录音过短；1.0.63仅修工具并重新执行。

实际初始OHCodec/Vulkan，3秒计时探针调用终局管理器；不声称真实GPU损坏。终局关联原sessionId1/loadGeneration1，旧release拒绝PLAYER_TERMINAL，recovery.ready后保留全局terminal锁存与旧Surface，创建新Surface的兼容会话2及3。两个后续实例实际software/no，有首帧/进度，正确释放，summary三首帧零非预期错误。

实际内录完整取回，四个音频区间通过：初始880Hz、故障后及重开440Hz且没有旧880Hz混播、最终关闭静音。原文件与音轨路径及哈希见identity.json。

本应用事件文件追加包含1.0.62的上一轮；events-all.jsonl保留原样，events.jsonl只取capture-started=1794591561734之后。分析仅绑定此次录音，未混用旧轮次。

这是独立诊断页的自动恢复流程；正式列表/选集交互由消费端API19TV验收，第4项保留。未覆盖永久平台Stop/Release挂起，也不证明物理扬声器音质。

后续T055已在1.0.65补齐实际手动返回与选片，见../t055-global/README.md；本目录仍保留自动流程旧证据，不混算为人工操作。
