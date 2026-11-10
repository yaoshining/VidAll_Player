# FFmpeg PR #11 接入记录

2026-11-11，消费已合并上游 SDK，未修改或构建 ohos_ijkplayer。

## 来源与兼容核验

- 合并提交 `32887363cb103163fe6557ca64c05539ad6d73f2`，独立浅克隆读取该提交的 32 项交付文件，与上游合并绑定摘要一致。
- SDK 归档 `eb069effc2ce51233186e5e033a2f8bf33f5317a27e4626ba50184807422aea0`，原始 manifest `7fd9cc6e5916b0b0b864e0c522e4134795774c1bb8c45e4f331d4788c17f4bbf`。SDK 目录和归档各 217 项逐项校验，包括符号链接目标内容。
- 六库导出集合逐项一致；142 个 mpv 原构建使用的 FFmpeg 头文件逐字节相同。为可靠故障通知补丁重建 mpv 并保留真实编译输入，当前 FFmpeg 运行库独立锁定。
- libavcodec 新增导入仅 NativeObjectReference/NativeObjectUnreference。官方 native SDK `native_window/external_window.h` 声明两者 introduced=8.0.0，Surface ID 查询 introduced=12.0.0，覆盖 API 19；未新增 Player API。
- Samba 两张 131072 字节字符表完整内容分别唯一匹配新 libavformat，偏移变为 4127144、4258216。公共 SMB 头内容不变。
- 正常 FFmpeg 六库来自上游无 TRACE/TEST/DIAGNOSTIC/EXPERIMENT 的构建；mpv 保持原 TRACE。编译宏按组件区分，旧 mpv 编译记录内的 FFmpeg 信息不冒充本轮 SDK 来源。

## TDD 和本地检查

先增加当前恢复 SDK 必须绑定、缺失/错误绑定三项回归，旧清单全部失败。接入及校验器更新后，28 项实际输入和篡改回归通过，包含旧库冒充恢复、伪造 SDK/merge、混用宏范围等负例。

49 项宿主门禁、9 项实际 mpv fence 函数、音频中断实际生产函数回归、5 项归档输入测试及外部来源审计通过。Spec Kit prerequisite 通过。

## 宪章与一致性

R6 → T016/T017 → 来源清单/独立绑定校验 → 实际输入正负例及 iMac CI。R7 → T018/T019/T020 → 设备同 PID 音画证据。R8 → T021 → API 19 与 API 20+ 音频中断回归。当前无新增 UI/权限/媒体协议或解码模式；正常保持 OHCodec/Vulkan 零拷贝。

此轮设备验收、CI 附件、PR 审查均待执行。上一轮 PID 32928 的平板记录对应旧六库和早于延迟回收修复的代码，不计作本轮通过。云真机浏览器当前登录/自动化访问尚未恢复；API 19 TV 模拟器已可启动。

## 旧审查补齐

- 事件队列满时丢失 owner 故障：先用实际源函数测试复现缺少可靠通知，再增加由 client 锁保护的独立故障槽，保留首个故障参数并在普通队列前消费。payload 归 client 持有，销毁 client 自动释放。测试覆盖满队列、重复故障、参数副本、其他 owner 不受影响和消费一次；ASan/UBSan 通过。没有新增公共 mpv 导出。
- 环境清理期间 TSFN 生命周期：实际 CleanupSessions 回归在原实现失败；现在清理钩子返回前同步封闭投递并释放 TSFN，耗时资源仍后台销毁。真实终局对象仍保留，回调通道先关闭。
- 真实 Initialize 回归覆盖 Vulkan 硬解获取隔离器、设置隔离选项、软件模式、非 Vulkan、名额耗尽及选项失败；纳入 native-entry 门禁。slow-release 用例增加 4.8–6.5 秒预算断言，旧任务仍阻塞时验证第二会话可执行。
- 测试线程按值捕获 gate，确保共享等待状态的生命周期。历史单次注入补丁指向原提交；解码模式计划明确正常硬解与上限降级范围。
- 命令/诊断超时永久隔离的两条旧评论已不适用于 1ae34e1 后实现：普通超时不会 Quarantine，关闭保持排队，成功完成才回收名额。明确 owner 故障仍发送所属会话错误。
- Surface ID 非复用尚待当前设备日志补证，任务表已据此更正。

最终本地门禁在补齐 parent-chain 的真实回调关闭函数后重新执行，49 项全部通过；输入审计 28 项、CI 合同 29 项通过。初次重跑的 parent-chain 因测试壳缺少新生产方法而编译失败，补齐实际函数提取后通过，未跳过断言。新的 mpv 两次独立构建均为 `c1997eee1f1190aca663e49ef86e98b96a1403cf5e2f99b16158cd217ef7d56a`，导出仍为原有 58 项。
