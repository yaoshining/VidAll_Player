# T054 关闭故障恢复：API24设备证据

1.0.61/API24 Mini，PID59902前后一致。诊断HAR为T053本地完整HAR，生产修复基线c7d56ee，非正式CI交付。真实OHCodec/Vulkan先执行关闭wait，再注入两次-4；不声称复现真实驱动故障。

A、B、C三个实例均实际OHCodec/Vulkan，身份和新Surface各自独立。A/C关闭失败后均手动返回列表并新开视频；B真实晚关闭7秒，release约5002ms返回且UI心跳前进25次。先确认同PID原生日志late-close completed real=0，再按确认，C仍硬解，证明名额回收。两隔离名额用满后D实际hwdec=no，仍有首帧和进度；runtime保持ready。

完整事件及实际内录通过29块、SHA256核验取回。八个音频区间全部通过：A/C为880Hz，B/D为440Hz，恢复新音中没有旧音混播，故障列表、晚关闭和最终关闭均静音。详见analysis.json、segments.json及native.txt。

仅API24平板诊断验证；不替代API19TV、永久Stop/Release挂起或正式消费者入口，也未单独证明物理扬声器音质。原始MP4/WAV路径和哈希见identity.json。
