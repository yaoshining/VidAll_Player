# 发布清单与门禁契约

验证构件先生成 `verification-manifest.json`，用于安装和 ARM64 TV 取证；只有全部发布门禁完成后，才能从同一不可变构件生成 `release-manifest.json`。后者才是 GitHub Release 附件、私有 ohpm 元数据和审批记录的共同事实来源。

```json
{"schemaVersion":3,"candidateId":"<immutable-candidate-id>","derivedFromVerificationArtifact":"<immutable-verification-id>","package":"@vidall/player","version":"0.0.0","sourceTag":"v0.0.0","sourceCommit":"<40位提交ID>","lockDigest":"<64位SHA-256>","target":{"abi":"aarch64-linux-ohos","compatibleApi":15,"api19Reviewed":true,"certificationApi":22},"artifacts":[{"path":"packages/vidall-player-0.0.0.har","sha256":"<64位SHA-256>","role":"consumer-package"},{"path":"packages/vidall-player/native/<module>.so","sha256":"<64位SHA-256>","role":"internal-napi","consumerDirectDependency":false},{"path":"third-party/libmpv.so","sha256":"<64位SHA-256>","role":"internal-runtime","consumerDirectDependency":false}],"nativeBinding":{"harPath":"packages/vidall-player-0.0.0.har","module":"<internal-napi-module>","abi":"aarch64-linux-ohos","loadEvidence":"har-native-packaging-spike.json","publicExportsOnly":true},"attestations":{"sourceProvenance":"provenance.json","sbom":"sbom.cdx.json","licenses":"licenses.json","notice":"NOTICE","capabilities":"capabilities.json","elfAudit":"elf-audit.json","compatibilityMatrix":"ijk-compatibility-matrix.json","consumerSmoke":"consumer-smoke.json","deviceEvidence":"arm64-tv-evidence.json"},"releaseNotesSha256":"<64位SHA-256>","status":"candidate"}
```

## API 审查基线

候选 SDK 的机器可读 API 审查基线固定在 `native/config/api-review.json`：API 15 为安装兼容下限、API 19 为敏感 API 审查点、API 22 为认证目标。基线状态为 `blocked-until-evidence`；必须分别附上 API 15 安装、API 19 审查和 API 22 认证证据。缺少任一证据时，清单不得标记为候选或发布通过。

## 不变量与状态

- `verification-manifest.json` 的验证构件 ID、`sourceCommit`、`lockDigest`、每个工件和附件的 SHA-256 创建后不可修改。它可供受控 consumer-smoke 与真机安装，但不能上传到发布渠道或标称候选。
- `candidateId`、`derivedFromVerificationArtifact`、`sourceCommit`、`lockDigest`、每个工件和附件的 SHA-256 在候选创建后不可修改；不得为任一发布渠道重新构建。
- `status` 只能由 `candidate` 转为 `published` 或 `failed`。发布前任一门禁失败或审批/凭据缺失，保持 `candidate` 或写入 `failed`，不得标记为发布成功。
- `published` 仅可在 GitHub Release 和批准私有 ohpm 源均回读到相同 `version`、`sourceCommit`、HAR SHA-256、SBOM SHA-256 与 `releaseNotesSha256` 后写入。回读收据不保存制品源地址、令牌或人员身份。

验证构件门禁：全量锁定 libmpv、FFmpeg 和直接/传递依赖、子模块、补丁、许可证来源、工具链/镜像与 SHA；HAR 安装、HAR 内部 NAPI/native 装入证明、HAR 与内部模块 ABI 绑定、SHA、ELF 架构/ABI、导出符号和动态依赖白名单，以及只导入公开 API 的独立 consumer-smoke。

候选门禁：验证构件门禁外，还必须具备 macOS/Linux clean build、SBOM、许可证结论、LICENSE/NOTICE、能力矩阵、API 15/19/22 记录、敏感信息扫描和 ARM64 真机证据。缺任何一项即阻断。

仅受保护 tag 可创建候选。批准后以同一清单上传 GitHub Release 与批准私有 ohpm 源，随后执行双渠道回读；当前 `native/scripts/build-libmpv-bootstrap.sh` 与 `.github/workflows/build-libmpv.yml` 是不可发布 bootstrap CI，不能生成或证明此 manifest。凭据仅在受控环境以最小权限注入。
