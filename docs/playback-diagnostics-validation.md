# Issue #79 验证记录

验证日期：2026-09-23。版本：0.1.0 未发布候选，schemaVersion=1。

- TDD：先运行新增 C++ 用例，缺少 diagnostics.h 失败；新增 ETS 主机会话用例先因 getDiagnostics 不存在失败；实现后通过。
- `bash native/tests/contract-baseline.test.sh`：通过，含 13 项 CTest 及既有契约/材料检查。
- `node native/tests/diagnostics-session.test.cjs`：通过，覆盖无调用不采样、并发合并、切源/表面/停止/释放过期、反复读取后停止及错误隔离。执行真实会话 ETS，NAPI 使用替身，不能代表设备表现。
- 新增原生转换测试：有效 0/false、单位转换、int64 最大值、负字节值、类型不符、NaN/Infinity、缺失、读取失败、不支持、隐去敏感字段通过。
- `devecocli build --modules vidall_player@default`：成功，包含 arm64-v8a 和 x86_64 原生库及诊断公开声明；后者仍是无播放能力的 probe。
- CodeLinter：SDK ETS 范围 17 个文件、0 defects、无检查错误。使用实际安装 SDK 24 / HarmonyOS 6.1.1（与构建工具使用的 bundled SDK 相同）；没有修改项目 target/compatible 配置。最初按项目目标版本调用 linter 找不到对应 SDK，改为实际 SDK 参数后检查完整成功。
- `git diff --check`：通过。

HAR：`packages/vidall-player/build/default/outputs/default/vidall_player.har`。

SHA-256：`2b0a9d774be2647c7886603c2c18b9c5239ca26596c9669241b0943d268b2852`。

CodeLinter 复现命令（macOS DevEco 默认安装位置；将 PROJECT 替换为当前仓库绝对路径）：

```sh
/Applications/DevEco-Studio.app/Contents/tools/node/bin/node \
  /Applications/DevEco-Studio.app/Contents/plugins/codelinter/index.js \
  --dir '["PROJECT/packages/vidall-player/src/main/ets"]' \
  --project PROJECT --config PROJECT/code-linter.json5 \
  --workdir /Applications/DevEco-Studio.app/Contents/plugins/codelinter \
  --sdkPath /Applications/DevEco-Studio.app/Contents/sdk \
  --sdkNumberVersion 24 --sdkStringVersion 6.1.1 --inIde true \
  --logPath /tmp/vidall-diagnostics-lint.log --language zh_CN
```

## 未完成的验收

TV 正由关联消费端任务占用，已协调不安装、不操作设备、不重启 hdc。本次没有生成或宣称真实设备快照。需在独占设备窗口验证本地/网络媒体、无音/视频、直播、缓存关闭、音轨切换、暂停恢复、seek、切源/退出、采样开关开销、硬解/Vulkan/DV/可用降级路径。PR 保留草稿，Issue #79 不关闭。
