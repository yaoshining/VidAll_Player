# 验证 #83

## 主线集成

在主线 PR 的检出目录运行以下命令。尺寸测试覆盖 Vulkan 更新、失败回滚、并发分离以及主线的运行时准入检查。

```sh
bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
python3 -B native/tests/vulkan-size/resize.test.py packages/vidall-player/src/main/cpp/napi_init.cpp
```

## 旧基线 HAR

需要重现 TV 消费端使用的兼容构建时，先检出[兼容分支归档](https://github.com/yaoshining/VidAll_Player/tree/32bb822)。在该归档的仓库根目录执行以下步骤。

1. 安装审计和测试依赖，执行 `npm ci --prefix scripts/test/legacy83-ci --ignore-scripts --no-audit --no-fund`。
2. 执行 `python3 -B scripts/test/legacy83-ci/audit.test.py`、`node scripts/test/legacy83-ci/workflow.test.cjs`、`python3 -B native/tests/vulkan-size/resize.test.py packages/vidall-player/src/main/cpp/napi_init.cpp` 和 `python3 -B native/tests/legacy-runtime.test.py`。原有 CTest 和 ArkTS 命令见归档中的 `docs/fixes/issue-83-legacy-vulkan-size.md`。
3. 本地可用 `devecocli build --modules vidall_player@default` 预验证。兼容分支的 GitHub Actions 在 iMac 自托管运行器上完整构建并上传 HAR。
4. 从[已验收包的构建记录](https://github.com/yaoshining/VidAll_Player/actions/runs/41640263079)获取 `legacy83-ci-har-2808387bca4f6f7bf2b2d2057e547f6708dd9035-1`。核对附件中的 manifest 和 SHA256SUMS，再对照[设备回执](evidence.md#最终设备回执)中的 HAR 与 HAP 哈希。
