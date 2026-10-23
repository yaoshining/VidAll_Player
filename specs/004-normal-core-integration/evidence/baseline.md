# TV 现用 HAR 与 Player 接入起点

日期：2026-10-23。结论：接入起点为 `951343145e076277be99f7b459ec614d5a64f8b8`。此远端 main 提交的完整 tree 与 `0ad5d6d3b52a39b342a50a413d4440f184107a22` 相同；原主工作树 main `ed7de980` 已落后，不作为本轮起点。

## 证据层级

1. TV `entry/libs/vidall_player.har` SHA256 为 `826b667dcd315e75e71f89065c3aef4bd60ea73743916ee629469f93228c66a9`。TV 交付提交为 `76f3a107264989814723eb1f128b9de5d8142079`。
2. 该 HAR 的 ARM64 native bridge `caaa94d86f2845b75a41220411fae9a7efdea79273d8acfa1aee10bbe387aa14`、mpv `3ae9969ac13a58aaa5827520a44e56461f566aff66b9bdd7fe4b78f0da31b076` 与 `0ad5d6d:docs/evidence/diagnostics79/retest-runtime.json` 历史实测记录逐字节相符。该记录描述 d91a38b 加 firstFrame surfaceGeneration 修复；后者已被 0ad5d6d 提交。
3. 在独立 checkout 对未修改的 951343 执行一次 `devecocli build --modules vidall_player` 成功。30 个 HAR 成员中 27 个字节相等，包含全部 ArkTS 声明、`modules.abc`、mpv、两架构 libc++。ABC SHA 为 `be79f9e5d3ffbfa05e7769e3adfacd4d99df238cb23234120a039986c29430aa`，当前源码的 ArkTS 构建结果精确匹配 TV。
4. `sourceMaps.map` 字节不同但 JSON 内容完全一致。ARM64 与 x86_64 native bridge 重建字节不同，`.text` 亦不同；不能表述为仅调试路径/build-id 差异。本轮不追求旧 native 哈希一致，历史 native 来源绑定与源码起点充分，保留当前宿主重建差异。

详细成员与 ELF 分段比较见本目录三个 JSON。构建日志位于独立私有证据目录，不包含在拟提交材料。新构建 HAR SHA 为 `a79ae22ab33721b879c1bddfeae33a7bb194f48a4b090b9b49c548ec68a069dc`，只用于基线核对，不是候选替换。

## 保护边界

原 Player 主工作树及索引、TV 全仓、旧候选和默认 SDK 不写入。独立 checkout 位于 `/private/tmp/phase32-player-integration-20261023/repo`，分支 `codex/004-normal-core-integration`。本轮只在该目录新增实现和产物。未修改 target API 22 / compatible API 15。新核心组合 API 24 工具链和目标设备覆盖不得推导为 API 15–22 全兼容。
