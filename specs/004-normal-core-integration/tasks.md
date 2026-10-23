# 任务清单

分支：`codex/004-normal-core-integration`。所有未完成项保持未勾选。

## 审查与基线
- [x] T001 核对 TV HAR、历史运行库与远端源码；一次受控基线构建，保存 ABC/声明精确匹配及 native 差异。
- [x] T002 在独立 codex 分支整理 spec、plan、公共契约与任务草案。
- [x] T003 审查 spec/plan/契约并完成 analyze 交叉核验；通过后才改产品源码。

## US1 / FR02–03、FR09–10：输入与初始化
- [x] T004 锁定 Phase30 A / Phase31 正常 8 库、头文件、静态 libplacebo、资源、源码/补丁/工具链/许可证；先写错库/缺库/禁宏/ABI 门禁 RED。
- [x] T005 审核新增 undefined API 与 API15/19/22/24 可用性，形成门控方案；不改 SDK 版本。
- [x] T006 公开初始化与真实 native 配置测试先 RED：重复、并发、异配置、缺资源、目录失败、SMB/terminal注册失败。
- [x] T007 最小实现进程初始化与完整核心输入，运行 GREEN 和旧回归。

## US2 / FR04–08：终局接管
- [x] T008 真实 session/NAPI 桥接 RED：先于 queue/锁的 fatal 检查，缓存诊断，阻塞命令、重复实例、晚到回调、release/join禁入。
- [x] T009 native deadline 实际子进程 RED：UI/回调/日志阻塞仍有界退出，未 opt-in 不退出且拒绝播放，变异负例拒绝。
- [x] T010 最小实现公共 fatal 契约、native 服务与异步桥接，GREEN、旧诊断/音轨/字幕回归。

## US3 / FR11–12：消费者与证据
- [x] T011 生成独立 HAR；公共根入口消费者构建与包内 9 库身份检查，不直接复制诊断 bridge。
- [x] T012 两次 clean HAR 与目标构建、逐成员差异归档；不追旧库哈希。
- [x] T013 独立签名消费者短场景：初始化/播放/seek/暂停恢复/关闭重开/应用终局接管，仅应用保屏。
- [x] T014 Spec analyze、来源锁/SBOM/许可证索引与边界核验；记录未验收及 TV 后续改动。
- [ ] T015 精确提交 clean 重放、独立审查和 SHA/文件/字节预览；用户批准前不 push。
- [ ] T016 批准后 CI 核对精确 SHA、结果与 artifact 身份，更新交接。

## 收尾结果
- T006–T010：真实源码 TDD、半创建回收、晚 load 提交、pending create/创建失败/终局回调边界完成；最终统一 host 重放记录见 evidence/host。原生旧回归另为 14/14。平台 API 仍为替身，不夸大为 GPU 故障验收。
- T011：最终规范化 HAR 已由独立公共根入口消费者实际构建/签名/运行，九库身份见 normalized-consumer-identity.json。
- T012：原始 clean-a/b 的 39 文件逐字相同，53 总成员只存在 mtime 封装差异；规范化 a/b 整包相同，13 项工具测试含危险输入和内容变异拒绝。
- T013：API24 电视正常短场景（两次首帧、暂停/恢复、20秒关键帧 seek、重开、保屏 false）、指定 NAS Basic 鉴权短播放与真实推进通过。独立 wrap 接缝的终局通知/保屏释放/退出请求及进程/Ability/窗口消失通过；宿主 kill 与 native 截止未独立区分，不算真实 GPU 故障。
- T014：来源外部闭包再次核验通过；历史保护基线比较通过，见 evidence/boundary-final.json；主仓 producer index 既有 stat 差异按原记录保留。
- T015：精确提交后在干净 checkout 重放，结果与提交 SHA 写入提交外 preview，最终独立审查由 root 完成；本提交中不预标通过。T016 远端 CI 等待精确 SHA 推送批准。
