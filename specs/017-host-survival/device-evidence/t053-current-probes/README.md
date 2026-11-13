# T053：当前音频修复的两组故障验收包

生产基线c7d56ee，封存输入T051；只追加既有关闭/全局诊断接缝，不改FFmpeg或TV。两份完整HAR由独立Player工程构建，消费HAP由本地MacBook Pro构建，不是正式CI交付。

- 1.0.58：Spec017新音频-关闭故障，HAP SHA256 c0ecf3dd76b948dd413e5cf7f93c1bc375496531a5dc8ab58bda36035acefa8b。
- 1.0.59：Spec017新音频-全局恢复，HAP SHA256 44945f7ac260f35890d3011c0804530a403a1d4980597f7bdc6f7b4c28c6aef7。

两组完整核心/ArkTS构建、输入无漂移、64项导出、诊断互斥、API20中断动态查找、HAR/HAP与实际展开依赖九库一致性通过；七个非mpv/bridge库逐字节等同c7d56ee原始iMac CI HAR，完整身份见tablet-preparation.json。现代共享userdata及官方库句柄回退都包含。

全局探针仍hardware-first；原硬件帧/owner/Surface/晚关闭/隔离上限和内录STARTED资格不变。工具使用T052的最多60秒授权等待，不改变生产故障截止。当前仅准备完成，未上传/未执行本轮两组故障，实际音轨尚未获得，不能替代API19 TV正式验收。导出能力和云端文件获取仍需实测确认。
