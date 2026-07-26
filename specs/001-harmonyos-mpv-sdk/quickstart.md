# 验证快速指南

本指南先验证可安装但不可发布的验证构件，再验证由其派生的候选制品；不代表当前仓库已经发布或通过真机认证。


## 0. 候选契约基线

在进入真实 bridge 或候选发布前，先运行以下本地门禁。该命令会检查唯一公开导出、原生会话生命周期边界、API 15/19/22 基线和 HAR 内部 native 装入的阻断记录：

```bash
bash native/tests/contract-baseline.test.sh
```

`release/audits/tdd-baseline.json` 记录公开契约的预期失败和修正后通过；可通过以下命令验证 loopback HTTP/WebDAV、认证、Range 与 chunked 夹具：

```bash
bash scripts/test/network-fixtures/network-fixtures.test.sh
```

`release/audits/har-native-packaging-spike.json` 状态为 `blocked` 时，真实 bridge 不得启用；构建成功、网络夹具或模拟状态机均不能替代 HAR 内部 native 装入和受控设备证据。

## 前置条件

- macOS 与 Linux 各一台干净环境，安装锁定的 DevEco SDK、Node/ohpm、C/C++ 工具链和审计工具版本。
- 一台 ARM64 HarmonyOS/OpenHarmony TV 真机，认证基线 API 22；可安装 API 15 兼容包。
- 受控测试素材、测试 WebDAV 服务与批准私有 ohpm 源权限；不得提交凭据或私人媒体。

## 1. 清洁构建与审计

1. 确认实现已提供完整 `native/config/sources.lock.json`，其锁定 libmpv、FFmpeg、所有传递依赖、补丁、许可证来源、工具链/镜像和 SHA-256；不得用当前 bootstrap 清单替代。
2. 在两个空工作目录分别执行实现后提供的 `scripts/build/reproducible-build.sh`；macOS 与 Linux 的来源提交、锁定摘要、目标 ABI 必须相同，字节差异必须写入构建记录并可解释。
3. 检查 `verification-manifest.json` 的 `aarch64-linux-ohos`、API 15/19/22、源提交、锁定摘要、HAR/native 工件 SHA 和装入/consumer-smoke 证明附件。
4. 执行 `scripts/audit/verify-release.sh <verification-manifest.json>`。
5. 预期：HAR、原生库、SHA、ELF 架构/ABI/符号/动态依赖审计和独立装入均通过；任一缺失返回非零并阻断验证构件。验证构件只用于后续真机取证，不得上传或标称候选。`native/scripts/build-libmpv-bootstrap.sh` 和 `.github/workflows/build-libmpv.yml` 仅为不可发布 bootstrap CI，不能用作本步骤的证据。

参见 `contracts/release-manifest.md`。

## 2. 隔离消费者冒烟

1. 创建独立 `consumer-smoke`，从受控验证构件安装 HAR；不得访问 `native/`，绝不修改 VidAll_TV。
2. 按 `contracts/arkts-sdk.md` 执行创建、附着有效 XComponent、加载可读本地 MP4、等待真实 `firstFrame`、播放和两次 `release`；消费者只能导入公开 HAR API，不能访问 `native/`、`entry`、私有 NAPI 或任何 VidAll_TV 内容。
3. 检查验证构件 manifest 的 `nativeBinding` 与 HAR 内容，确认内部 NAPI/native 模块随 HAR 装入且 consumer 没有直接依赖它；归档装入、命令和回调结果。
4. 销毁并重建画面后重复播放；再以无效 URI 与已释放会话调用命令，并检查每个会话的事件序号严格递增、旧 generation/epoch 事件被丢弃且关闭后不再投递。
5. 预期：真实首帧、事件递增、重建不使用旧世代、无效输入产生脱敏结构化错误、重复释放无崩溃死锁或悬垂回调；任何 API 19 后能力在 API 15--18 的降级行为均有能力证据记录。

## 3. ARM64 真机门禁

1. 在 API 22 ARM64 TV 安装 API 15 兼容包，登记安装结果；核验敏感 API 的 API 19 审查和 API 15--18 降级。
2. 对同一验证构件连续执行 100 次“创建 -> 附着 -> 加载 -> 播放 -> 跳转 -> 暂停 -> 释放”，记录崩溃、死锁、释放后回调和存活会话数；任何一次失败阻断从该构件创建候选。
3. 执行本地 MP4、HTTP/HTTPS、WebDAV、HLS、DASH、SMB localhost HTTP 样本，记录真实首帧、跳转、缓冲恢复、CPU、内存、错误和释放。
4. 对 HTTP/WebDAV 记录认证头是否仅在同信任范围转发、跨范围重定向是否剥离，以及 Range、超时与恢复结果；对 SMB proxy 记录匿名 lease 的取得、续期、释放请求、释放确认、过期和异常清理结果。
5. 验证多音轨、内嵌/外挂/网络字幕、字体缺失、硬解回退、断网重试、后台恢复及十次连续轨道切换和跳转。
6. 以遥控器验证示例的焦点、方向、确认、返回、列表边界与错误重试。
7. 预期：矩阵只使用“已通过真机样本”“已构建待验证”“不支持或暂缓”。API 19 TV 模拟器结果只能标为兼容辅助；未实测 4K、10-bit、60fps、HDR 与高规格音频不得标记支持；ARM64 真机证据缺失不得进入发布审批。

参见 `data-model.md` 与 `contracts/compatibility-matrix.md`。

## 4. 双渠道发布回读

1. 在验证构件通过 ARM64 真机、清洁构建、SBOM/许可证、能力矩阵和敏感信息门禁后，由受保护 tag 从该不可变构件创建候选，禁止手工重建或替换附件。
2. 运行受控工作流上传 GitHub Release 与批准私有 ohpm 源。
3. 回读比较版本、源提交、组件 SHA、SBOM 与发布说明。
4. 预期：完全一致才为 `published`；任一失败保持候选/失败，且不得称已发布。
