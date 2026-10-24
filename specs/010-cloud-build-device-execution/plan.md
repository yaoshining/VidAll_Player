# 分阶段最小实施计划

## A：云端默认构建与无签名编译（先实施的本地范围）

复用当前工作流的可信来源与actual事件SHA绑定；明确默认调用vidall_player@deveco26，不改产品target/API。保留旧锁/脚本作为历史证据，退役旧normal自动self-hosted目标及其旧AND结果的自动触发；不能把新结果命名伪装成旧锁构建通过。新组合统一显式AND，包括完整宿主、目标HAR、消费者、Hypium编译、清理；旧工作流契约测试须按新职责更新，先RED。

旧test-player独有完整CTest迁入云端host（可独立job/step，避免仅重复已有诊断）；其ArkTS/Hypium编译在同一已核macos-26 SDK会话中新增临时工程。复制精确entry主/测试资源和9suite，输入改为本次HAR，保持API22/15与编译model；临时配置明确unsigned、禁用本机签名发现，产品仓文件不改。旧libentry桥是否为有效依赖要由源import/真实编译证明，不能盲移除；若构建需该桥则单独记录旧桥与九库检查范围，不能混称正常核心九库。

真实运行devecocli编译entry@ohosTest，校验实际测试模块元数据、module名、测试runner/suite汇入、依赖解析与源hash、签名状态、输出唯一性及cleanup。若无签名SDK能力不足，保留实际失败，采用经官方任务定义证明的无签名编译阶段并明确“只编译未打包”；不得以skip或stub编译代替。test_module_built只有实际成功产物才真，compilePassed与signedInstallable分别记录。

拟改文件：normal-core.yml、deveco26-pr82-gates.yml、test-player.yml；新scripts/test/cloud-build/（覆盖门禁/unsigned Hypium helper及测试），deveco26-gates必要汇总/工作流测试；原normal-workflow/signing测试仅改职责相关断言。旧bootstrap/锁/产品源码八库不动。build-libmpv迁移在B前置未闭环时不擅自删。

## B：producer源码构建职责交接（根审计后定实施边界）

明确FFmpeg/OHCodec/mpv/libplacebo/静态依赖精确源码、补丁、SDK、功能/ELF/许可证验证及run/artifact摘要；生产端云端构建负责生成，Player只绑定已批准输入并做集成核验。保留Player源脚本/来源历史及全部可移植契约。#7/#8真实目标历史、#9宿主结果与当前004输入分别列出，不合并成一个虚构全绿来源。

最小方案供根审查：明确退役Player两条历史生产入口、保留脚本/旧锁/宿主来源与许可证契约；新增硬门禁只允许当前004精确八库及manifest基线，任何核心更新必须另交producer精确源码/补丁/工具/实际目标制品与功能证据，未具备则直接拒绝。当前组合不重建、不改库；这属于生产职责明确交接，不声称#9已完成新全量目标。若根不接受该阶段边界，则B保持阻塞，不能通过简单skip冒称全部构建迁云。必要producer代码变更另行精确预览，当前不越仓修改。

## C：云端设备包与iMac手动执行（先方案，不启用）

普通consumer缺少实际媒体，只能保留编译用途。新增独立device-package staging，复用normal-core-consumer公共初始化/terminal主体，在固定rawfile/test_video.mp4注入短合成媒体；云端绑定生成器/参数/媒体SHA和HAP来源，缺媒体失败关闭。不得使用私人NAS影片、签名或未批准二进制代替fixture。

先确定专用测试bundle、测试集、profile设备白名单、证书指纹/有效期及签名工具锁。最小优先方案是iMac受控签名既有云端unsigned包，绝不调用编译工具；核unsigned→signed除签名块外有效载荷/九库/媒体/API均不变，签名完成后核profile/证书/设备授权。不扫描或自动复用旧开发签名，当前iMac未发现CI签名材料，需用户供专用bundle profile。云端签名是另一个后续选项，本轮不自行配置任一方式。

云端仅交付审定run/attempt对应unsigned HAP和文本manifest；固定workflow/源head/merge/来源锁/工具/九库/API/HAP与媒体SHA。signed包和可能含设备profile的材料不进入公开Player Actions artifact；存储/签名权限与保留期精确预览另批。已有公共文本artifact不等于可装包。

iMac仅专用label（拟vidall-device-imac，不创建），默认分支手动dispatch与独立环境review，no PR/push自动触发。可信控制器固定已审版本及工具SHA，输入只接受数字run/artifactID、完整commit/hash、固定bundle/测试模式；禁止任意URL/路径/脚本、禁止checkout PR内容后执行。即使包来自受审PR，控制器仍来自独立固定受信任版本；不运行包内脚本。下载/校验可在云端先做，iMac再核ZIP/HAP，签名阶段显式受控；任何时候不调用build/ohpm/npm/CMake。

设备资源用专用并发组且cancel-in-progress=false，额外本机互斥避免跨workflow争用。固定serial/HDC身份；offline/未授权/缺签名输出待验，不宣称成功。新入口执行初始化/terminal/应用保屏，结束核本进程/窗口/保屏释放；只清理本次文件/端口映射，不改系统或全局HDC。normal/Hypium/diagnostics场景分别白名单，不直接运行旧假网络/旧同步事件播放用例。当前可先做无凭据的artifact控制器契约/未就绪判定TDD，不安装设备或签名。

## 验证与停止点

TDD先真实旧工作流缺覆盖/签名决定built等RED；实现后测试官方runner限定、旧目标退役不丢检查、Hypium缺模块/错HAR/API/旧缓存/编译失败/缺签名、汇总缺证/skip拒绝。设备控制器在C获准后用实际函数mock平台：错run/head/来源/签名/包摘要/设备离线/超时/并发/清理失败均拒绝或待验，不能用job绿色冒充真机通过。

本地完成后根审查、冻结精确提交、一次必要clean真实构建重放与清理、推送预览；云端环境允许ref/批准SHA更新不沿用f28aa，另批。签名、runner标签和正式required/ruleset切换单独阶段批准。当前只完成specify/plan/task和覆盖映射，待根审后才动实现。
