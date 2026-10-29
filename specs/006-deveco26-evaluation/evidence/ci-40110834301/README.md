# DevEco26 首次官方 ARM64 CI 持久证据

本目录保存 run [40110834301](https://github.com/yaoshining/VidAll_Player/actions/runs/40110834301) 的选择性原始公开文本与脱敏摘要，绑定提交 `610dd1f6e83fa844a7096de20ce591b72e48e9da`。它证明的是该提交的独立 `push` 评估，不是 PR #82 当前 merge 结果或发布验收。

- [run-summary.json](run-summary.json)：运行、job、每步结论、artifact、临时 Secret 删除状态及验收范围；由实际 API 记录提取，不含 Secret 值。
- [context.json](context.json)、[evaluation-result.json](evaluation-result.json)：精确 HEAD/tree/tracked 内容、19项工具文件身份、固定八库、API、真实编译/链接与 HAR 记录。
- [bootstrap-result.json](bootstrap-result.json)：完整官方归档和 DMG hash、CLI锁及现场资源快照；`persistentSourceVerified=false` 保持。
- [runner-setup.log](runner-setup.log)：真实 Hosted `macos-26-arm64` 镜像身份。三个测试日志记录41项契约、21项准备/清理、6项真实 CMake/目标 Clang 回归；[workflow-tests.log](workflow-tests.log) 记录13项变异。
- [cleanup-result.json](cleanup-result.json)、stop/unmount 日志和退出码：隔离 home 的 daemon 12686 停止、只读挂载消失。临时下载 Secret 已删除并由两个审查通道回读确认不存在。
- [independent-review.json](independent-review.json)：审查者另行下载同一 ZIP，对 GitHub digest、全部33项索引及关键内容独立核验通过。
- [pr82-baseline.json](pr82-baseline.json)：2026-10-25的只读 PR/ruleset 快照；可随远端变化，实施前必须刷新。

原 artifact ID `12566429056`，ZIP 233289字节，SHA256 `01bf591e8dec7cc14c80e0a13c70c8d55e19c5feaba21d7333356455c751e179`。原 ZIP含33项索引文件及index本身；[artifact-original-index.json](artifact-original-index.json) 保留原索引。本目录只复制相关选择项，未复制大量导出符号文本，也不包含 SDK、HAR、HAP、签名、媒体或原始设备日志，不能当完整原 ZIP。

[evidence-index.json](evidence-index.json) 记录每个持久选择项的来源、字节数和 SHA256；标记 `unchanged=true` 的项与已核原文件逐字节相同。远端 artifact 有保留期限，以上核心内容随仓库保存；无需依赖本机临时路径重读关键结论。证据索引不包含自身和本说明，避免循环hash。

保留限制：本地与云端 bridge/HAR摘要不同，尚未独立归因，不宣称跨主机可重复构建；下载来源只验证了一次获批的短期官方链接，临时Secret已删除；consumer/低API真机/HDR/主观声画继续待验，`formalArtifactAllowed=false`。
