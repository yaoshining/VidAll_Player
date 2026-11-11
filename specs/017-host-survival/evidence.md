# 实施与验证记录

日期：2026-11-11。分支 `codex/host-survival-contract`，基线 main `fa27cbd346f1a745ffc1b5bfd57b4239c094327f`。本记录是首个实现切片，不是全局故障恢复验收。

## TV 协作

已创建 [VidAll_TV #372](https://github.com/yaoshining/vidall-tv/issues/372)，承接单视频兼容记忆、重启后的选择、提示、故障归属处理和 API 19 TV 正式入口回归。

## TDD

1. `node native/tests/host-survival/compatible.test.cjs`：实现前失败，compatible 仍传 auto，缺少第五个原生播放模式参数；实现后通过。执行真实 createPlayer / PlayerSession / bridge，仅替换平台 NAPI。
2. `python3 native/tests/ohcodec-fence/initialize.test.py`：实现前新增五参数调用无法编译；实现后编译真实 Initialize，验证 GPU 存在时兼容模式仍选择 software、无硬解名额、hwdec=no/interop=no、非法模式和关键选项失败。原硬解/两名额上限仍通过。
3. 真实 NAPI CreateSession 提取测试增加 compatible、旧四参调用及非法模式用例，验证新参数确实转发到 Initialize，非法模式不创建会话。
4. `python3 native/tests/surface-resize/sw.test.py packages/vidall-player/src/main/cpp/napi_init.cpp`：修复前 fence-ready/fence-timeout/fence-request-failed/fence-invalid 四项失败，其余原用例通过；修复后通过，并补充持续 EINTR、POLLHUP 用例，共 14 场景。用真实 pipe/poll/fd 关闭及提取的生产 SwRenderLoop；NativeWindow 为平台替身，不是真实 GPU fence。

## 验证结果

- `python3 scripts/test/normal-core/run.py --out <新目录>`：51/51 通过，包括上述兼容模式及 SW fence、原生入口、隔离名额、回调清理、旧终局保护和破坏性变异检查。既有退出契约仍保留，因此旧 deadline 测试通过不代表“不退出”要求已实现。
- GL 渲染/尺寸回归：12 场景通过。
- `native/tests/completion-event.test.py`：通过，覆盖 EOF 唯一性、非 EOF、媒体身份、晚到及线程交错。
- 音频中断生产函数测试：从 Phase30 A 的只读封存源选取所需文件，在临时目录应用本仓原有 `0001-ohaudio-legacy-interrupt.patch`，执行 `native/tests/audio-interrupt/interrupt.test.py <临时源目录>`，通过。本次未改 FFmpeg 或其仓库，未重建 libmpv/FFmpeg，不把此宿主结果称为新设备验收。
- `devecocli build --product default --modules vidall_player@deveco26`：本机 MacBook Pro / arm64 编译通过，HAR 为 ARM64 目标，仅本地预验证，非 CI 交付。首次误用不存在的 product deveco26 已更正为 default product + deveco26 module target。
- 构建有 HAR applyToProducts 不生效、既有原生库类型声明、clang unused gcc-toolchain 参数告警；无编译错误。未修改这些无关配置以消除告警。
- Spec Kit prerequisites 与 `git diff --check` 通过；宪章/一致性人工检查见 checklists/constitution-and-consistency.md，未完成门禁仍保留未勾选。

## 当前明确未完成

1. 全局 owner_tag 是不透明 hw 对象标签，当前 API 没有稳定的 session/load 映射；不能把它转换为媒体 ID，也不能猜测标记当前页面。T013 未完成。
2. 当前 mpv 终局回调契约明确不能在 handler 内查询/停止/释放 mpv。OHAudio 写回调与旧焦点尚无通过验证的终局隔离入口；不能假设发 pause/stop 就能穿越已挂起的 core/VO 锁。T009 待完成原生音频隔离及独立兼容会话实测。
3. 原两个隔离名额不覆盖全部软件会话/线程，需 T004 总预算设计；未改变 deadline、全局硬解禁令或强行释放策略。
4. `devecocli device list` 当前无连接设备；未执行本轮模拟器/真机音画测试。无 API 19 TV 验收。
5. 未推送本次分支、未创建 PR、无新 CI HAR；TV 不应接入本地包作为最终交付。
