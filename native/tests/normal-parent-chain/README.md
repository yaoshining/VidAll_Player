# NativeSession 父级链验证

运行：`python3 -B native/tests/normal-parent-chain/run.py --out /private/tmp/player-parent-chain-run`。

测试逐字提取当前 `napi_init.cpp` 的构造、析构、`Release`、`StopRendererLocked`、`DestroyRenderer`、`CloseCallbackLocked`、`DeleteSession` 和 `CleanupSessions`；与真实 `process_runtime.cpp` 编译。对象使用真实 `std::thread`、`std::shared_ptr`、`std::unique_ptr`，正常退出必须完成线程 join 和各平台释放事件。终局后禁止记录关键销毁事件，进程只能在明确 deadline 后以 86 退出；超时和错误退出都拒绝。

平台 mpv/NAPI/EGL/Window 函数为记录事件和注入边界的替身，成员壳与 Start/render 线程主体也是最小调度替身；不声称逐字测试完整 RenderLoop，不代表真实 GPU 永不返回或物理画面验证。

callback 场景以真实条件变量阻塞生产者通知交付线程，在调用 receiver 之前暂停；logger 场景填满真实 pipe 后阻塞独立审计写线程。二者用于证明独立 native monitor 不依赖这些线程；不冒称已让真实平台 logger 或 SDK 内用户 callback 挂死。

## Deadline 门禁

用子进程 `steady_clock` 同域的首次锁存/输出时间差，加宿主实时读取触发标记到 wait 返回的耗时，验证触发到退出为 `deadline - 10ms` 至 `deadline + 500ms`。10ms 是时间量化与 pipe 交接容差，500ms 含父进程 wait/poll 调度余量。不能用进程启动时间代替触发时间，也不能跨语言直接相减两个时钟 epoch。

变异仅修改本次输出目录的编译副本，不改产品文件：

- `--mutate destroy-guards --case terminal-render-tail --case terminal-during-render-free` 必须因禁止销毁事件失败。
- `--mutate deadline-immediate --case terminal-callback-delivery-blocked --case terminal-logger-blocked` 必须因提前退出失败，即使退出码也是 86。
- `--mutate deadline-missing --case terminal-callback-delivery-blocked --case terminal-logger-blocked` 必须因 timeout 失败。
- `--mutate deadline-exit` 可复核退出码错误会失败。

每轮记录原始与实际编译函数、runtime、模板、runner 的 SHA，并保存完整子进程事件和结果。
