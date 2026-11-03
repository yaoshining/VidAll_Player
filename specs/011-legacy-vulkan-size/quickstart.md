# 验证步骤

1. 执行 `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`，确认当前 feature 是 `011-legacy-vulkan-size`。
2. `npm ci --prefix scripts/test/legacy83-ci --ignore-scripts --no-audit --no-fund`。
3. 执行 `python3 -B scripts/test/legacy83-ci/audit.test.py`、`node scripts/test/legacy83-ci/workflow.test.cjs`、`python3 native/tests/vulkan-size/resize.test.py packages/vidall-player/src/main/cpp/napi_init.cpp`、`python3 native/tests/legacy-runtime.test.py`。原有 CTest 和 ArkTS 命令见 `docs/fixes/issue-83-legacy-vulkan-size.md`。
4. 本地预验证可通过 `devecocli build --modules vidall_player@default`；其产物仅供预验证。
5. 推送 `codex/legacy-vulkan-size-83`，等待 GitHub 托管 `macos-26` 的 `旧基线 Vulkan 修复 HAR（云端 Mac CI）`；失败时查日志，不交付失败包。
6. 从该 run 下载 `legacy83-cloud-har-<提交>-<尝试>`，验证 manifest 提交/run 与 SHA256SUMS。向 TV 会话交付该 CI 包。
7. 消费端以相同哈希完成模拟器→云平板/TV 回归，记录 Vulkan 尺寸变化、连续操作、退出/重进。失败时记录现象，保持 #84 未开始。
