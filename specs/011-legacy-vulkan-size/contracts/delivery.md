# #83 交付契约

## 播放器

公开初始化和 ArkTS 接口不变。Vulkan 当前代际的有效 Resize 必须同时提交窗口 geometry 与 `ohos-surface-size`。失败必须返回失败且不认可新尺寸。其他后端与 completed 行为不变，不引入进程退出策略。

## CI

提交必须等于 GitHub Actions 的事件 SHA，repository 必须是 `yaoshining/VidAll_Player`，run 与 attempt 必须有效。完成测试、完整工程构建、库哈希及 ABI 检查后才能上传 `vidall_player-issue83-ci.har`、`manifest.json` 和 `SHA256SUMS`。不得以脚本替换归档成员或上传本地包冒充 CI 输出。

固定输入定义在 `scripts/test/legacy83-ci/inputs.json`；原 HAR 的库集合、libmpv/runtime 哈希、bridge 导入/依赖是比较基准。发现漂移必须失败并调查，不自动升级依赖。无跨项目触发步骤。

## 消费端

通知包含 run URL、sourceCommit、文件和库哈希。消费端先核验身份并保留原包回退，再依次执行模拟器与云平板/TV 回归。CI 成功不是 #83 设备验收完成，更不是 #84 的提前合入授权。
