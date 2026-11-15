# 宿主存活：资源与回调边界审查

## 范围与结论

本轮检查 `session_budget.h`、`work_budget.h`、`session_isolation.h`、`process_runtime.cpp`、`host_recovery.c`、真实 NAPI/ArkTS 入口及锁定 mpv 输入中的 `audio/out/ao_ohaudio.c`。这是源码和宿主回归证据，不是 API 19 TV 零拷贝、系统音频焦点或真实故障恢复验收。

原有会话、执行器和异步命令预算不能约束事件生产者。真实 `SetEventCallback` 使用无限 TSFN 队列，JS 不消费时 `Dispatch` 每次分配一个事件；原有 ArkTS 节流发生在消费之后。阻塞消费者后发送 20,000 个快照的真实入口测试复现了无界积压。T030 将其改为有限邮箱与唤醒票据。

## 资源额度及归还点

| 资源 | 上限 | 归还条件 |
| --- | --- | --- |
| NativeSession | 标准 6、旧兼容 2、新恢复代 2 | 原生对象真实析构；删除 handle、隔离或调用方超时均不归还 |
| 原生操作预算 | 常规 32、关闭 8、恢复 8 | 最后一个实际任务引用结束；超时完成 NAPI Promise 不归还 |
| 独立执行器 | 硬解 2、标准 6、兼容 2、恢复 2、运行期配置 1 | 工作/关闭退出；隔离的在途任务继续占用其额度 |
| ArkTS 命令等待 | 每 Player 64 | 完成或关闭队列拒绝调用方；不因此释放原生任务 |
| 音频登记 | 16 槽 | 平台 Release/Destroy 确认成功；停止/失败/未知状态仍占槽 |
| 回调代邮箱 | 常规 32、新恢复代独立 8 | Session、TSFN finalize、排队/在途票据全部放弃引用 |
| 每个邮箱 | 待交付 64 条、256 KiB 字符串有效载荷；单事件 64 KiB | 交付或关闭后释放；取出的批次仍占当前回调代 |

回调代按实例创建时固定的运行期代选择池。全局故障后旧实例不能借用恢复额度；旧池 32 个未 finalize 的回调代全部保留时，新恢复代仍可登记 8 个。反复重注册或释放/新建都不能绕过额度。超过额度返回 `CALLBACK_RESOURCE_LIMIT`；注册新回调前先申请额度，失败时保留原有效回调。

每个 TSFN 至多排一张唤醒票据。JS 正在处理取出的批次时，生产者可再填一个批次，因此上限按两批计算：每邮箱 **128 条、512 KiB**，40 个邮箱合计 **5,120 条、20 MiB 字符串有效载荷**；最多 **80 张唤醒票据**（各一张在途、一张排队），另有固定数量的 TSFN finalize 持有者。容量检查在消息复制前完成，插入临时值也计入待交付批次预算。超大消息先检查长度，不先复制后截断。

上述字节数仅统计邮箱持有的 `type`、`message` 字符串有效载荷，不是 RSS 精确上限，不包含 STL/字符串容量、引用计数、固定元数据、NAPI 转成 JS 对象后的内存、调用方原始字符串或 mpv/系统服务内部分配。不能以它承诺进程总内存的精确峰值。

## 事件交付与失败语义

- `position`、`subtitleText`、`videoParams`、`audioParams`、`tracks` 合并为最新快照。替换时移到队尾，保留与关键事件的 sequence 先后关系。
- 正常容量内 `state`、`error`、`fileEnd` 按顺序交付。无法容纳下一条时，待交付批次替换为固定的 `PLAYER_EVENT_QUEUE_FULL` 错误，明确宣告本会话事件交付失败；后续状态不得覆盖该错误。
- 失败会话不再接受普通操作、帧获取或回调重注册；释放仍走原有安全路径，新 Player 不继承该错误。失败不触发进程终局，不解锁 OHCodec，也不强制销毁隔离资源。
- 原生异步操作在入口、执行线程及实际执行器开始任务前检查准入，覆盖“上一操作阻塞 → 新命令排队 → 邮箱失败 → 解除阻塞”的窗口。
- `PLAYER_EVENT_QUEUE_FULL` 属于整个桥会话，ArkTS 不按旧媒体 epoch 或 Surface 代过滤。收到事件或原生操作返回该码都会进入 error、拒绝后续命令；晚到事件不会重启播放。
- 用户监听者异常按监听者隔离并记录固定上下文，下一监听者仍接收事件。意外穿透到 NAPI 的 pending exception 由 `napi_get_and_clear_last_exception` 清除，记录固定日志后继续批次，后续 EOF/错误仍可达；日志不包含用户抛出的文本。
- 票据只持有邮箱及事件所需的生命期标记，不持有或解引用 `NativeSession`。关闭、重注册、环境清理、隔离和全局旧代检查仍逐事件执行。JS 为空时仅销毁持有物，不访问环境。

## 红绿回归

先复现后修复的失败包括：无限唤醒队列、首个 JS 回调抛异常导致后续 EOF 不可达、执行器等待期间的邮箱失败未阻止命令执行、失败会话仍可获取帧、错误码映射丢失，以及切源提升 epoch 后唯一溢出事件被忽略。

可重跑命令：

```sh
python3 native/tests/ohcodec-fence/callback-cleanup.test.py
python3 native/tests/normal-native-entry.test.py /tmp/vidall-t030-entry queued-event-overflow event-overflow-release
python3 native/tests/completion-event.test.py
node native/tests/host-survival/event-overflow.test.cjs
```

回调入口测试使用真实方法提取、可控 TSFN 排队替身和 ASan/UBSan，覆盖高频积压后错误/EOF、快照顺序、条数/字节/超大消息溢出、在途批次同时入队、在途关闭、32/8 全局额度、先 finalize 后消费旧票据、关闭/重注册/空环境/跨环境/旧代与隔离回调。NAPI 测试逐字编译实际 `QueueNative`、`GetFrameData`、创建和释放入口；ArkTS 测试加载真实桥、PlayerSession 和状态机，覆盖跨 epoch 失败、失败后拒绝复用、释放新建、注册失败清理和两监听者异常隔离。以上接入 `scripts/test/normal-core/run.py`，全量结果由主任务统一记录。

## 仍需单列的边界

音频域必须先证实旧音频停止，才能发布新兼容代 ready；音频恢复线程与 UI/NAPI 通用池分开。永久阻塞的系统 Stop/Release 不得通过假报 ready 或释放未知资源绕过。本次还发现 API 19 旧音频回调持有全局登记读锁跨越回调的风险，由 T032 独立修复和重建核心；T030 不构成该项完成证明。

`preserve-host` 保留应用，`controlled-app-exit` 的历史退出策略仍按显式契约存在。T030 没有修改两种运行期策略或 FFmpeg。真机上的系统音频独占、OHCodec/Vulkan 全局故障后新代音画，以及 API 19 TV 正式入口连续故障验收仍须独立记录；宿主测试或模拟器 software/no 不能替代这些结果。


## T035：已静止音频与残留资源分别计数

每个音频槽新增受登记锁保护的 `quiescent` 事实。平台 Stop 已确认成功，或 Renderer Release 返回成功后，旧音频不再计入恢复 pending；Builder_Destroy 后续失败或阻塞时，槽仍保持占用，AO 与 builder 不释放。失败状态不能覆盖已确认的静止事实。新槽初始化清除该事实，旧 token 无权标记新槽；16 个槽总预算不变。

恢复扫描只尝试取得槽控制锁，忙槽保留状态并由现有恢复线程下一轮重试，不新增线程、不阻塞其他槽。真实生命周期测试覆盖 builder 失败/阻塞、Release 未返回及两者交错，并填满剩余 15 槽确认残留资源没有提前归还；普通控制调用结束后，下一轮确实执行 Stop。该修复只处理已知安全状态被清理失败覆盖的问题，不宣称未知 Stop/Release 永久阻塞也能续播。
