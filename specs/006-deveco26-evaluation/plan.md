# 实施计划

新增独立deveco26工具锁/包装器/下载挂载准备与契约测试，复用旧ci-target的输入、HAR、编译命令、快照纯函数，不修改旧默认逻辑。CLI1.3.4使用已验证的随包Node和绝对wrapper入口，clean前锁定DEVECO_CLI_STUDIO_PATH。未获来源闭包时不生成虚假归档hash；完整下载的计算hash明确与独立厂商发布hash区分。

先RED表达新profile、下载200/206语义、错误/缺证/泄密边界，再最小GREEN；冻结本地候选后实际clean/HAR，主agent独立审查。因产品配置/八库不改，新增桥接动态依赖、C++符号和包内API元数据审查是必要验证。旧锁在新SDK上拒绝为预期RED，不能改旧锁变绿。

官方runner仅独立评估；长期自动来源尚缺。完整归档在RUNNER_TEMP核验后提取DMG，删除自己的ZIP再只读挂载，记录磁盘/内存和错误；仅临时目录可清理，不改系统。默认target22/compatible15和Hvigor模型保持，若构建失败需产品变更先报告。
