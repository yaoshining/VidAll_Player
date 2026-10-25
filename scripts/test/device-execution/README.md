# 本机设备执行前置预检（Spec010 C）

`controller.py` 实现制品预检、签名前后 ZIP 有效载荷比较和本机互斥，单独运行始终返回 `pending`。本轮新增 `executor.py`、`imac.py` 和 `signer-helper/`，提供固定短测事务与本地签名/验签/设备适配器；用法和授权边界见 [EXECUTION.md](EXECUTION.md)。这些新增能力目前仅完成宿主测试，真实签名、口令可用性和设备输出格式仍待验，不能将宿主GREEN当真机通过。

## 本地验证

```sh
python3 -B scripts/test/device-execution/controller.test.py
```

测试只使用临时目录中的合成 ZIP、合成库/媒体字节和真实操作系统 `flock`。它们验证本程序的真实函数和跨进程互斥，但不代表可安装 HAP、平台签名、设备连接或播放通过。临时测试目录会清理。运行不访问网络，不读取私有 NAS 配置或签名材料。

CLI 的退出码为：`1` 输入校验失败；`2` 前置预检后仍待验收。当前不会返回设备验收成功的 `0`。

```sh
python3 -B scripts/test/device-execution/controller.py \
  --artifact /path/to/approved-artifact.zip \
  --approval /path/to/independently-approved-envelope.json \
  --approval-sha256 <外部批准的完整-envelope-SHA256> \
  --lock /path/to/owner-only-directory/tv-device.lock \
  --device-state unknown
```

调用者必须从独立审批取得 `--approval-sha256`，不能临时计算包内或未审查 envelope 的摘要后自行授权。`--device-state` 是调用者提供的观察，不是本程序实测；输出始终标记 `deviceStateIndependentlyVerified=false`。实际执行入口 `imac.py` 另行核验设备与工具身份；本预检接口自身不做实时观察。

## 两层绑定，避免循环自证

外层 ZIP 必须只包含 `manifest.json` 和 `device-unsigned.hap`。包内 manifest 不允许自带 artifact ID 或整个 ZIP 的 digest。由上传完成后的外部审批 envelope 绑定这些字段。

`source` 在 envelope 和 manifest 中必须逐项相同，键为：

```text
repositoryId, repository, workflowPath, workflowSHA,
runId, runAttempt, event, headSHA, eventMergeSHA,
sourceTreeSHA, sourceTrackedBytesSHA256, toolchainLockSHA256,
releaseSourceLockSHA256, inputHAR_SHA256
```

仓库固定为 `yaoshining/VidAll_Player` / `1307243374`。所有提交/树标识为 40 位小写十六进制，摘要为 64 位 SHA256。工作流路径为 `.github/workflows/<名称>.yml`。`merge_group` 的 headSHA 必须等于实际 group checkout/eventMergeSHA，而非某个 PR head。工作流、run attempt、head 和实际 merge 均需明确；不使用 `latest`、分支名或客户端猜测的 merge 替代它们。

外部 envelope 的字段（均必需且不允许额外字段）：

```text
schemaVersion: 1
source: 上述来源对象
artifactId: 正整数
zipSHA256: 整个下载ZIP的SHA256
manifestSHA256: 包内manifest原始字节的SHA256
approvedBundleName: 审批的隔离测试bundle
approvedMode: normal-local-smoke
github: 独立回读的来源/制品元数据
```

`github` 精确含 `repositoryId, artifactId, runId, runAttempt, headSHA, eventMergeSHA, workflowPath, workflowSHA, conclusion, expired, digest`。前八项必须与 envelope 一致，`conclusion=success`、`expired=false`，`digest=sha256:<zipSHA256>`。本程序不联网查询 GitHub；这些回读数据必须由上游可信流程取得，并连同 envelope 整体经过独立审批。包内文字或任意调用者伪造的 JSON 不能替代这一步。

manifest 的精确字段：

```text
schemaVersion, source, hap, bundleName, moduleName, abilityName,
api, libraries, media, test
```

- `hap`：`path=device-unsigned.hap`、正整数 `bytes`、`sha256`。
- `moduleName=entry`，`abilityName=EntryAbility`。`module.json` 必须实际包含相同 app bundle、module、唯一入口 ability 和 API；只检查 manifest 声明不算通过。
- `api`：`minAPIVersion=50003015`、`targetAPIVersion=60002022`，保留产品 API 基线。
- `libraries`：九个库名到 SHA256 的映射。要求实际 HAP 仅有 `libs/arm64-v8a/` 下的同一组九库：八个既有核心库和 `libvidall_player_native.so`；不允许缺库、加库或其他架构。
- `media`：精确含 `path, bytes, sha256, generatorSHA256, parameters, origin`。路径固定 `resources/rawfile/test_video.mp4`、`origin=generated-synthetic`；核对实际媒体字节。生成器 SHA 和参数由独立审批绑定，不根据媒体文件名推断来源。
- `test`：精确含 `mode=normal-local-smoke`、`entrySourceSHA256`、`privateNasAllowed=false`、`freshSessionRequired=true`。

测试 fixture 的 `setUp` / `repack` 提供完整可执行数据结构示例。它们的所有字节都是测试替身，不能拿来生成真实批准记录。

入口源码摘要、合成媒体声明和 HAR 输入摘要需要上游构建与审查证据，本程序只检查其格式和外部绑定，不能从已编译 ArkTS 反推出源码。后续执行必须使用新的独立 session，不复用旧 NAS 计划或凭据；**当前没有执行这一步，不能据 manifest 的布尔值宣称它已完成**。

## ZIP 与签名边界

读取前限制单个归档 128 MiB、展开总量 512 MiB、成员数 4096。拒绝路径逃逸、非规范路径、重名成员、符号链接/特殊文件、加密和不支持的压缩；只在内存读取，不向磁盘解包。JSON 也拒绝重名键与非有限数字。

`compare_signed_payload(unsigned, signed)` 对比双方全部 ZIP 成员的名字和解压后原始字节。标准 HAP 签名块不属于 ZIP 成员，不需要豁免任何成员；`META-INF` 等新增/变更成员也会被拒绝。

有效载荷相等不证明签名真实性。这个函数始终返回 `signatureVerified=false`。后续仍需真实官方 `hap-sign-tool verify-app` 成功，并把签名工具、已批准证书/profile、设备范围、签名前后 HAP 摘要绑定到验证记录。自称 `signatureVerified=true` 的配置不会让 `preflight` 放行，缺少官方适配器时继续 `official-signature-verifier-not-connected`。

## 互斥与剩余工作

`DeviceLease` 使用文件系统 `flock`，父目录必须属于当前用户且不可被组或其他用户写入，锁文件必须为本人拥有的单链接普通文件且仅本人可读写。拒绝末级符号链接。所有针对同一设备的调用者必须约定同一个锁路径；当前接口不会自己选择设备。释放时保留锁文件 inode，只解锁关闭，避免 unlink 引起两把锁。预检只在检查期间持锁；它不是跨越未来签名/安装动作的持久预约。

离线、未授权、未知设备、锁占用、缺少签名配置都有明确 `pendingReason` 和 `nextRequired`。剩余真实设备执行、签名、部署、清理、官方工具身份核验、现场 HDR/听音均继续待验收。本目录不改系统设置，不替换候选，不访问 TV/Player 产品工作区。
