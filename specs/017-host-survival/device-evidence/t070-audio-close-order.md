# T070：时钟采样线程关闭锁序复核

基线main `fa27cbd346f1a745ffc1b5bfd57b4239c094327f`，核对head `42776c0f68f59b360cf3966fc6db70cc6bb92bc3`。本轮核对“关闭持control锁再join、采样线程等待control”的可能死锁。

## 当前实现与调用链

- `0012-ohaudio-clock-outside-callback.patch`中，`uninit()`先`unbind_legacy()`，再`stop_timing_worker()`发布停止请求并join，最后调用`mp_host_audio_remove()`。
- `native/mpv/host_recovery.c`的`mp_host_audio_remove()`才获取槽`control`，持锁调用`release_for_recovery()`；该释放回调没有调用`stop_timing_worker()`。
- 退休扫描持槽锁调用的是`stop_for_recovery(renderer)`，仅查询状态、Stop及确认状态，不join时钟线程。mpv父级`ao_uninit()`在调用驱动uninit之前已经结束缓冲线程，没有持有host音频槽锁；init失败清理也不持该锁。
- `timing_worker()`取得control后再次读取timing_stop，因此停止请求发布后不会继续新发起平台查询。已经进入的平台查询若永久不返回，join会保留AO、renderer、线程与槽，这属于已披露平台调用挂起边界，不是上述相互等待死锁。

交付源绑定：`native/tests/audio-interrupt/ci-input-lock.json`锁定`ao_ohaudio.c` SHA-256 `169a4481e56375e62d954f4b11a9d99017fb0cfac78eea05fb11a21656af63de`，与生产构建源实际比较一致；对应libmpv SHA-256 `405ce871811e9956fce593a19651a8f50b826a8ff46612881646f0c7685afa21`。未使用T066诊断插桩源代替生产源。

## 确定性回归

新增`native/tests/host-survival/audio-close-order.test.py`原样提取交付源的reset、采样线程、停止/join、uninit、释放与退休Stop函数，链接仓库真实`host_recovery.c`和pthread锁/join。仅平台调用使用替身，调度屏障加在函数边界。

| 场景 | 本地结果 | 必须成立的事实 |
| --- | --- | --- |
| 错误锁序负例 | EXPECTED_DEADLOCK，退出73 | 将join移入持control的release回调后，采样线程进不了control，关闭不能完成；确认到指定死锁标记，不接受编译失败或其他崩溃冒充负例 |
| 正常关闭时采样线程即将获取control | PASS | join开始时remove尚未进入；放行采样线程后关闭完成且不新查询 |
| 退休Stop持control、关闭并发等待采样线程 | PASS | 平台Stop未返回时不Release，pending保持；Stop返回后扫描、采样与关闭完成 |
| 平台查询在途 | PASS | join期间对象/槽保留；查询实际返回后释放一次且槽可复用 |
| 无时钟线程/重复uninit | PASS | 释放恰好一次，不出现无效join或双重销毁 |

ASan/UBSan启用。音频CI接入约束先红后绿，避免新增脚本未执行；CI从固定上游独立派生并核验同一音频源后执行测试，日志保存为`close-order.log`。当前生产关闭顺序已符合S40，因此本轮只补测试、CI和规格证据，未修改或重建mpv/FFmpeg，也未改变核心九库。

## 结论与边界

在已核对head及交付源中，所述“关闭持control再join”的P1路径不成立；故意制造该顺序的负例可稳定检出。不能据此宣称平台Stop/查询永久挂起已解决；#93、API19 TV正式入口、x86_64完整产物及既有设备边界仍保留。本轮CI结果在PR后续回执中绑定最终提交，旧CI不替代新测试结果。

Todoist步骤`6j2fmV64v5vjrCFG`；负责会话修复 issue #89 / local / 01a1bccc-e2cc-7a13-8cd6-31aae7079fb0。

## CI回执

提交`0e4c8b1a2a25c1a4b75a944b9bf76798d37edf7b`：[音频/诊断CI43721487483](https://github.com/yaoshining/VidAll_Player/actions/runs/43721487483)成功，公开日志明确记录`mutant-cycle EXPECTED_DEADLOCK`及四个正向PASS；原有音频、中断、尺寸/旋转/完成事件回归继续通过。[102项组合宿主43721487549](https://github.com/yaoshining/VidAll_Player/actions/runs/43721487549)、原生来源43721487624和[iMac分支43721480908](https://github.com/yaoshining/VidAll_Player/actions/runs/43721480908)成功；iMac完成HAR、独立消费者和Hypium编译，实际runner为`yaoshiningdeiMac`。合并预览及之后仅文档提交的最终状态继续按各自SHA核对，不把这笔回执当成未来提交通过。
