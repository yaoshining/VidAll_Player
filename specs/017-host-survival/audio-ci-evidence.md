# 音频 CI 输入与恢复回归

本切片对应 T005/R5：CI 必须测试当前交付核心的音频源，不能使用仅应用旧 #89 补丁的源码配合新恢复测试。先复现旧步骤失败，再校验锁定基线、相关恢复补丁、派生源码摘要和交付核心身份；旧中断回归与恢复 data/control/lifecycle 均需运行。没有修改 FFmpeg 或重建核心，平台替身结果不替代系统焦点及真机声音。

2026-11-11 红测：检出 ErBWs/mpv `6edeee00a07b9b76f197aa71eee3d029fb090de4`，仅应用 `0001-ohaudio-legacy-interrupt.patch` 后运行 `interrupt.test.py`，退出 1，报 `缺少生产函数 release_for_recovery`。原步骤无法覆盖 Spec 017 当前音频集成。


修复后的 `prepare-audio-ci-input.py` 在独立目录复制测试实际读取的 7 个文件；核对上游 commit、基线文件、现有恢复输入锁中的全部补丁/新增源码与交付 libmpv 哈希，只应用命中这 7 个文件的补丁片段，最后比对派生文件摘要。摘要来自构建 `814e4f02ced52a15a213fd9a0c54f37ffbbe6ca466df758bd04ab0a9fa901beb` 时的完整锁定输入，实际逐文件比对通过。旧 checkout 不变，摘要错误或补丁失败不发布半成品目录。不把这 7 文件派生结果当成完整 mpv 构建输入。

新回归先因准备脚本缺失失败；补脚本后仅工作流接入断言失败，再修改工作流至绿色。9 项测试覆盖正常派生、原始输入不变、重复输出、缺补丁、源文件/补丁/新增恢复源码篡改、错误交付核心、错误上游 commit、路径越界及双事件路径过滤。`test-player.yml` 的 pull_request 和 push(main) 都覆盖 phase30、native/mpv、准备脚本、恢复锁、交付核心；新测试锁由 native/tests 路径覆盖。

本地执行命令及结果（MacBook Pro / Darwin arm64）：

- `python3 -B native/tests/audio-interrupt/ci-input.test.py`：9 项通过。
- `python3 -B native/tests/audio-interrupt/prepare.test.py`：4 项通过，未提供独立 Phase30 归档的 1 项明确跳过；没有将其计为验证通过。
- `python3 -B native/scripts/prepare-audio-ci-input.py --source <锁定上游检出> --output <新目录>`：通过，7 文件与完整交付源匹配。
- `python3 -B native/tests/audio-interrupt/interrupt.test.py <新目录>`：实际生产函数编译及中断/换集回归通过。
- `python3 -B native/tests/host-survival/audio-data.test.py <新目录>`：6 个 ASan/UBSan 回归通过。
- `python3 -B native/tests/host-survival/audio-control.test.py <新目录>`：旧代禁止启动、实际 Stop、正常暂停恢复及失败状态通过。
- `python3 -B native/tests/host-survival/audio-lifecycle.test.py <新目录>`：8 个 ASan/UBSan 回归通过，包括 Generate/Release 阻塞与失败保留。
- `node scripts/test/cloud-build/workflow.test.cjs`：现有工作流契约及 9 + 11 项变异拒绝通过。

CI 现在将上述四组音频回归指向同一派生目录，并保留失败/成功日志和文件摘要，使用 `pipefail` 防止 tee 掩盖失败。远端 Ubuntu 实际执行尚待推送或 PR 触发；本次没有重新构建或更换 HAR/原生库。上述宿主平台替身不证明真实焦点释放、系统 Stop 有界返回或 API 19 TV 真机续播。


## T032：旧回调等待不占全局登记锁

红测使用此前锁定源：真实 legacy 登记/回调函数在宿主编译，分别阻塞旧写入和旧中断回调，另一 AO 都无法在 1 秒观察窗口内完成 bind/write/interrupt/unbind，断言 `旧回调不应阻塞其他 AO 的登记/注销` 失败。最初夹具的额外 unused-parameter 告警已按生产编译规则配置，随后取得上述行为红测；未把编译失败当成行为证明。

新增 `0006-isolate-legacy-audio-callbacks.patch` 在 0005 后应用，仅改变 mpv 的 OHAudio legacy 登记。短全局 mutex 保护查找与每 binding 的 in_flight 引用；平台写入/暂停回调在解锁后执行。注销先从表中移除，然后用条件变量仅等待自身引用归零，等待释放全局 mutex；没有超时强行释放 AO。引用达到 UINT_MAX 时拒绝增加；token 不复用，关闭中的同一 AO 不能重新登记。

`legacy-lifetime.test.py` 的四例在 ASan/UBSan 下通过：write-blocked、interrupt-blocked、two-callbacks、overflow。前两例证明旧回调明确仍在等待时，另一 AO 能独立完成完整登记与注销；two-callbacks 同时保留写入和中断，先放行写入，确认旧注销仍未完成，再放行中断；各例同时覆盖从表撤销后的迟到 token、同一 AO 地址重新登记及重复注销。overflow 验证引用不回绕，拒绝的写回调返回静音、不触及 AO。

原 `interrupt.test.py` 保留全部中断/换集/迟到事件/等待释放断言，夹具由“rwlock 必须忙”改为当前实现的“全局 mutex 可取得、该 AO 的在途引用为 1”，不要求新实现继续保留原来的全局阻塞。它在旧源、新候选源均通过。新候选上的 data 六例、control、lifecycle 八例通过；新工作流断言先失败，再接入 legacy-lifetime 回归，九项输入/工作流测试复验通过。

冻结补丁 SHA-256：`d35a126644500e410e79b81fcea80e5f5536ec524e07083ade489f99ebe1893e`；音频源 SHA-256：`2bfe14e207371a1c7a30805582302b35b9b6550c47a80340b7c79f8980e861cc`。补丁可独立叠加且与候选逐字节相同。负责完整构建的主任务已重建并绑定 mpv SHA-256 `46cd4112ac963a935773d70fe8fec4254753c9ceade6f546c6433c40318815e7`；本回归重新对该新锁定输入执行四例，并核对七个音频测试文件与候选、更新后的 CI 输入锁完全一致。

这解决 API 19 legacy 全局登记锁的跨会话阻塞，不移除自身回调排空等待，也不改变平台 Stop/GetState/Release 永久阻塞时仍须保留资源的安全限制。尚无真机声音、系统焦点或 API 19 TV 正式入口通过结论。
