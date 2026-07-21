# 发布清单与门禁契约

每个候选版本必须生成 `release-manifest.json`，它是 GitHub Release 附件、私有 ohpm 元数据和审批记录的共同事实来源。

```json
{"schemaVersion":1,"candidateId":"<immutable-candidate-id>","package":"@vidall/player","version":"0.0.0","sourceTag":"v0.0.0","sourceCommit":"<40位提交ID>","lockDigest":"<64位SHA-256>","target":{"abi":"aarch64-linux-ohos","compatibleApi":15,"api19Reviewed":true,"certificationApi":22},"artifacts":[{"path":"packages/vidall-player-0.0.0.har","sha256":"<64位SHA-256>"},{"path":"native/libmpv.so","sha256":"<64位SHA-256>"}],"attestations":{"sourceProvenance":"provenance.json","sbom":"sbom.cdx.json","licenses":"licenses.json","notice":"NOTICE","capabilities":"capabilities.json","elfAudit":"elf-audit.json","compatibilityMatrix":"ijk-compatibility-matrix.json","deviceEvidence":"arm64-tv-evidence.json"},"releaseNotesSha256":"<64位SHA-256>","status":"candidate"}
```

## 不变量与状态

- `candidateId`、`sourceCommit`、`lockDigest`、每个工件和附件的 SHA-256 在候选创建后不可修改；不得为任一发布渠道重新构建。
- `status` 只能由 `candidate` 转为 `published` 或 `failed`。发布前任一门禁失败或审批/凭据缺失，保持 `candidate` 或写入 `failed`，不得标记为发布成功。
- `published` 仅可在 GitHub Release 和批准私有 ohpm 源均回读到相同 `version`、`sourceCommit`、HAR SHA-256、SBOM SHA-256 与 `releaseNotesSha256` 后写入。回读收据不保存制品源地址、令牌或人员身份。

候选门禁：全量锁定 libmpv、FFmpeg 和直接/传递依赖、子模块、补丁、许可证来源、工具链/镜像与 SHA；macOS/Linux clean build；HAR 安装、SHA、ELF 架构/ABI、导出符号和动态依赖白名单；SBOM、许可证结论、LICENSE/NOTICE、能力矩阵、API 15/19/22 记录、敏感信息扫描和 ARM64 真机证据。缺任何一项即阻断。

仅受保护 tag 可创建候选。批准后以同一清单上传 GitHub Release 与批准私有 ohpm 源，随后执行双渠道回读；当前 `native/scripts/build-libmpv-bootstrap.sh` 与 `.github/workflows/build-libmpv.yml` 是不可发布 bootstrap CI，不能生成或证明此 manifest。凭据仅在受控环境以最小权限注入。
